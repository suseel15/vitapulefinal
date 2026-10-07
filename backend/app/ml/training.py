from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

from app.ml.features import FEATURE_NAMES, FEATURE_SCHEMA_VERSION, extract_features

METADATA_FIELDS = {
    "athlete_id", "session_id", "exercise", "sensor_placement",
    "device_id", "sampling_rate_hz", "source",
}
SAMPLE_FIELDS = {"session_id", "timestamp", "ax", "ay", "az", "gx", "gy", "gz"}
LABEL_FIELDS = {"session_id", "start_ms", "end_ms", "exercise", "label_provenance"}
ALLOWED_PROVENANCE = {"MANUAL", "CLINICIAN_REVIEWED"}
ALLOWED_EXERCISES = {
    "REST", "WALK", "SQUAT", "SIT_TO_STAND", "LEG_RAISE",
    "CALF_RAISE", "HAMSTRING_BRIDGE", "BALANCE", "UNKNOWN",
}
PSEUDONYM = re.compile(r"^[A-Za-z0-9_-]{8,80}$")


def build_feature_rows(dataset: Path, *, window_ms: int = 3000, step_ms: int = 1000) -> list[dict[str, Any]]:
    metadata = _read_csv(dataset / "metadata.csv", METADATA_FIELDS)
    samples = _read_csv(dataset / "samples.csv", SAMPLE_FIELDS)
    labels = _read_csv(dataset / "labels.csv", LABEL_FIELDS)
    metadata_by_session: dict[str, dict[str, str]] = {}
    for row in metadata:
        session = row["session_id"]
        if not session or session in metadata_by_session:
            raise ValueError("metadata.csv must contain one non-empty row per session_id.")
        if row["source"] not in {"LIVE_SENSOR", "SIMULATION"}:
            raise ValueError(f"Session {session} has an unsupported data source.")
        if not PSEUDONYM.fullmatch(row["athlete_id"]) or not PSEUDONYM.fullmatch(row["session_id"]):
            raise ValueError("Dataset athlete_id and session_id must be pseudonymous IDs, not names or email addresses.")
        if not row["device_id"]:
            raise ValueError(f"Session {session} is missing its device identifier.")
        rate = _finite(row["sampling_rate_hz"], "sampling_rate_hz")
        if rate <= 0 or rate > 100:
            raise ValueError(f"Session {session} has an unsupported sampling rate.")
        metadata_by_session[session] = row

    samples_by_session: dict[str, list[dict[str, Any]]] = {}
    for row in samples:
        session = row["session_id"]
        if session not in metadata_by_session:
            raise ValueError(f"Sample references unknown session {session}.")
        parsed = {"timestamp": _finite(row["timestamp"], "timestamp")}
        parsed.update({axis: _finite(row[axis], axis) for axis in ("ax", "ay", "az", "gx", "gy", "gz")})
        samples_by_session.setdefault(session, []).append(parsed)

    labels_by_session: dict[str, list[dict[str, Any]]] = {}
    for row in labels:
        if row["session_id"] not in metadata_by_session:
            raise ValueError(f"Label references unknown session {row['session_id']}.")
        if row["label_provenance"] not in ALLOWED_PROVENANCE | {"SYNTHETIC_SIMULATION"}:
            raise ValueError("Rule-generated labels are not ground truth; use reviewed labels or synthetic simulation provenance.")
        if row["exercise"] not in ALLOWED_EXERCISES:
            raise ValueError(f"Unsupported labeled exercise class: {row['exercise']}.")
        if metadata_by_session[row["session_id"]]["source"] == "SIMULATION" and row["label_provenance"] != "SYNTHETIC_SIMULATION":
            raise ValueError(f"Simulation session {row['session_id']} must use SYNTHETIC_SIMULATION labels.")
        if metadata_by_session[row["session_id"]]["source"] == "LIVE_SENSOR" and row["label_provenance"] == "SYNTHETIC_SIMULATION":
            raise ValueError(f"Live session {row['session_id']} cannot use synthetic labels.")
        start, end = _finite(row["start_ms"], "start_ms"), _finite(row["end_ms"], "end_ms")
        if start < 0 or end <= start:
            raise ValueError("Label intervals must be positive and ordered.")
        labels_by_session.setdefault(row["session_id"], []).append({**row, "start": start, "end": end})

    result: list[dict[str, Any]] = []
    for session, session_samples in samples_by_session.items():
        ordered = sorted(session_samples, key=lambda sample: sample["timestamp"])
        if any(right["timestamp"] <= left["timestamp"] for left, right in zip(ordered, ordered[1:])):
            raise ValueError(f"Session {session} contains duplicate or unordered sample timestamps.")
        session_labels = labels_by_session.get(session, [])
        cursor = 0
        while cursor < len(ordered):
            start = ordered[cursor]["timestamp"]
            end = start + window_ms
            window = [sample for sample in ordered if start <= sample["timestamp"] <= end]
            if len(window) >= 20 and window[-1]["timestamp"] - start >= window_ms * 0.8:
                overlapping = [
                    label for label in session_labels
                    if label["start"] <= window[0]["timestamp"] and label["end"] >= window[-1]["timestamp"]
                ]
                if len(overlapping) == 1:
                    features = extract_features(window, expected_rate_hz=10.0)
                    if features["sampling_rate_hz"] >= 8.0:
                        result.append({
                            **features,
                            "athlete_id": metadata_by_session[session]["athlete_id"],
                            "session_id": session,
                            "exercise": overlapping[0]["exercise"],
                            "sensor_placement": metadata_by_session[session]["sensor_placement"],
                            "label_provenance": overlapping[0]["label_provenance"],
                            "dataset_provenance": (
                                "SYNTHETIC_SIMULATION"
                                if metadata_by_session[session]["source"] == "SIMULATION"
                                else "LIVE_SENSOR_REVIEWED"
                            ),
                        })
            next_time = start + step_ms
            while cursor < len(ordered) and ordered[cursor]["timestamp"] < next_time:
                cursor += 1
    if not result:
        raise ValueError("No labeled windows met the minimum sample and label-coverage requirements.")
    return result


def write_feature_rows(rows: list[dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "athlete_id", "session_id", "exercise", "sensor_placement",
        "label_provenance", "dataset_provenance", *FEATURE_NAMES,
    ]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def train_random_forest(
    feature_csv: Path,
    output_dir: Path,
    *,
    model_version: str = "rf-exercise-v1",
    random_seed: int = 17,
    allow_synthetic: bool = False,
) -> dict[str, Any]:
    try:
        import numpy as np
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
        from sklearn.model_selection import GroupShuffleSplit
    except ImportError as error:
        raise RuntimeError(
            "Model training requires the optional dependencies; install with pip install -e '.[ml-training]'."
        ) from error

    rows = _read_csv(feature_csv, {"athlete_id", "session_id", "exercise", "sensor_placement", *FEATURE_NAMES})
    provenance = _dataset_provenance(rows)
    if provenance == "SYNTHETIC_SIMULATION" and not allow_synthetic:
        raise ValueError("Synthetic movement data requires explicit allow_synthetic=True and is not production evaluation.")
    subjects = {row["athlete_id"] for row in rows}
    labels = {row["exercise"] for row in rows}
    if len(subjects) < 3 or len(labels) < 2:
        raise ValueError("Training needs at least 3 pseudonymous athletes and 2 exercise classes.")
    features = [[_finite(row[name], name) for name in FEATURE_NAMES] for row in rows]
    targets = [row["exercise"] for row in rows]
    groups = [row["athlete_id"] for row in rows]
    feature_matrix = np.asarray(features, dtype=np.float64)
    split = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=random_seed)
    train_indices, test_indices = next(split.split(feature_matrix, targets, groups))
    train_subjects = {groups[index] for index in train_indices}
    test_subjects = {groups[index] for index in test_indices}
    if train_subjects & test_subjects:
        raise RuntimeError("Subject-independent split invariant failed.")
    train_labels = {targets[index] for index in train_indices}
    test_labels = {targets[index] for index in test_indices}
    if train_labels != labels or test_labels != labels:
        raise ValueError("Subject-independent split must contain every exercise class on both sides; collect more labeled athletes.")

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=8,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=random_seed,
        n_jobs=1,
    )
    model.fit(feature_matrix[train_indices], [targets[index] for index in train_indices])
    expected = [targets[index] for index in test_indices]
    predicted = model.predict(feature_matrix[test_indices]).tolist()
    classes = sorted(labels)
    metrics = {
        "dataset_provenance": provenance,
        "accuracy": float(accuracy_score(expected, predicted)),
        "classification_report": classification_report(expected, predicted, labels=classes, output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(expected, predicted, labels=classes).tolist(),
        "classes": classes,
        "train_subject_count": len(train_subjects),
        "test_subject_count": len(test_subjects),
        "test_subjects": sorted(test_subjects),
        "train_sample_count": len(train_indices),
        "test_sample_count": len(test_indices),
    }
    artifact = {
        "format": "vitapulse-random-forest-json-v1",
        "model_name": "RandomForestExerciseClassifier",
        "model_version": model_version,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_names": list(FEATURE_NAMES),
        "classes": classes,
        "supported_sensor_placements": sorted({row["sensor_placement"] for row in rows}),
        "minimum_sampling_rate_hz": 8.0,
        "recommended_sampling_rate_hz": 10.0,
        "status": "EXPERIMENTAL",
        "metrics": metrics,
        "trees": [_export_tree(model, tree) for tree in model.estimators_],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / f"{model_version}.json"
    _write_json(artifact_path, artifact)
    checksum = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    evaluation_path = output_dir / f"{model_version}.evaluation.json"
    _write_json(evaluation_path, metrics)
    return {"artifact_path": str(artifact_path), "evaluation_path": str(evaluation_path), "sha256": checksum, **metrics}


def train_1d_cnn(
    feature_csv: Path,
    output_dir: Path,
    *,
    model_version: str = "cnn-exercise-v1",
    random_seed: int = 17,
    allow_synthetic: bool = False,
) -> dict[str, Any]:
    try:
        import numpy as np
        from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
        from sklearn.model_selection import GroupShuffleSplit
    except ImportError as error:
        raise RuntimeError(
            "Model training requires the optional dependencies; install with pip install -e '.[ml-training]'."
        ) from error

    rows = _read_csv(feature_csv, {"athlete_id", "session_id", "exercise", "sensor_placement", *FEATURE_NAMES})
    provenance = _dataset_provenance(rows)
    if provenance == "SYNTHETIC_SIMULATION" and not allow_synthetic:
        raise ValueError("Synthetic movement data requires explicit allow_synthetic=True and is not production evaluation.")
    subjects = {row["athlete_id"] for row in rows}
    labels = {row["exercise"] for row in rows}
    if len(subjects) < 3 or len(labels) < 2:
        raise ValueError("Training needs at least 3 pseudonymous athletes and 2 exercise classes.")

    features = [[_finite(row[name], name) for name in FEATURE_NAMES] for row in rows]
    targets = [row["exercise"] for row in rows]
    groups = [row["athlete_id"] for row in rows]
    feature_matrix = np.asarray(features, dtype=np.float64)
    split = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=random_seed)
    train_indices, test_indices = next(split.split(feature_matrix, targets, groups))
    train_subjects = {groups[index] for index in train_indices}
    test_subjects = {groups[index] for index in test_indices}
    if train_subjects & test_subjects:
        raise RuntimeError("Subject-independent split invariant failed.")
    train_labels = {targets[index] for index in train_indices}
    test_labels = {targets[index] for index in test_indices}
    if train_labels != labels or test_labels != labels:
        raise ValueError("Subject-independent split must contain every exercise class on both sides; collect more labeled athletes.")

    classes = sorted(labels)
    class_to_index = {label: index for index, label in enumerate(classes)}
    train_values = np.asarray([features[index] for index in train_indices], dtype=np.float64)
    test_values = np.asarray([features[index] for index in test_indices], dtype=np.float64)
    train_targets = np.asarray([class_to_index[targets[index]] for index in train_indices], dtype=np.int64)
    train_mean = train_values.mean(axis=0)
    train_scale = train_values.std(axis=0)
    train_scale[train_scale < 1e-8] = 1.0
    train_values = (train_values - train_mean) / train_scale
    test_values = (test_values - train_mean) / train_scale

    filter_count = 8
    kernel_size = min(5, len(FEATURE_NAMES))
    rng = np.random.default_rng(random_seed)
    kernels = rng.normal(0.0, math.sqrt(2.0 / kernel_size), size=(filter_count, kernel_size))
    convolution_biases = np.zeros(filter_count, dtype=np.float64)
    dense_weights = rng.normal(0.0, math.sqrt(2.0 / (filter_count + len(classes))), size=(filter_count, len(classes)))
    dense_biases = np.zeros(len(classes), dtype=np.float64)

    windows = np.lib.stride_tricks.sliding_window_view(train_values, kernel_size, axis=1)
    for _ in range(250):
        convolution = np.einsum("npk,fk->npf", windows, kernels) + convolution_biases
        activations = np.maximum(convolution, 0.0)
        max_positions = activations.argmax(axis=1)
        pooled = activations.max(axis=1)
        logits = pooled @ dense_weights + dense_biases
        logits -= logits.max(axis=1, keepdims=True)
        probabilities = np.exp(logits)
        probabilities /= probabilities.sum(axis=1, keepdims=True)
        probabilities[np.arange(len(train_targets)), train_targets] -= 1.0
        probabilities /= len(train_targets)

        dense_gradient = pooled.T @ probabilities
        dense_bias_gradient = probabilities.sum(axis=0)
        pooled_gradient = probabilities @ dense_weights.T
        activation_gradient = np.zeros_like(activations)
        rows_index = np.arange(len(train_targets))[:, None]
        filters_index = np.arange(filter_count)[None, :]
        winning_activation = activations[rows_index, max_positions, filters_index]
        activation_gradient[rows_index, max_positions, filters_index] = (
            pooled_gradient * (winning_activation > 0.0)
        )
        convolution_gradient = activation_gradient
        kernel_gradient = np.einsum("npk,npf->fk", windows, convolution_gradient)
        convolution_bias_gradient = convolution_gradient.sum(axis=(0, 1))

        learning_rate = 0.03
        dense_weights -= learning_rate * dense_gradient
        dense_biases -= learning_rate * dense_bias_gradient
        kernels -= learning_rate * kernel_gradient
        convolution_biases -= learning_rate * convolution_bias_gradient

    expected = [targets[index] for index in test_indices]
    inference_artifact = {
        "format": "vitapulse-1d-cnn-json-v2",
        "classes": classes,
        "feature_names": list(FEATURE_NAMES),
        "normalization_mean": train_mean.tolist(),
        "normalization_scale": train_scale.tolist(),
        "conv_kernels": kernels.tolist(),
        "conv_biases": convolution_biases.tolist(),
        "dense_weights": dense_weights.tolist(),
        "dense_biases": dense_biases.tolist(),
    }
    from app.ml.cnn import OneDCNNJsonModel

    inference_model = OneDCNNJsonModel(
        {
            **inference_artifact,
            "model_name": "OneDCNNExerciseClassifier",
            "model_version": model_version,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "status": "ACTIVE",
            "minimum_sampling_rate_hz": 8.0,
            "supported_sensor_placements": sorted({row["sensor_placement"] for row in rows}),
        },
        expected_schema=FEATURE_SCHEMA_VERSION,
    )
    predicted = []
    for index in range(len(test_indices)):
        prediction = inference_model.predict(
            features[test_indices[index]],
            sampling_rate_hz=10.0,
            sensor_placement=rows[test_indices[index]]["sensor_placement"],
            quality_acceptable=True,
        )
        if prediction is None:
            raise RuntimeError("The trained CNN rejected a holdout sample that passed training validation.")
        predicted.append(prediction.label)
    metrics = {
        "dataset_provenance": provenance,
        "accuracy": float(accuracy_score(expected, predicted)),
        "classification_report": classification_report(expected, predicted, labels=classes, output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(expected, predicted, labels=classes).tolist(),
        "classes": classes,
        "train_subject_count": len(train_subjects),
        "test_subject_count": len(test_subjects),
        "test_subjects": sorted(test_subjects),
        "train_sample_count": len(train_indices),
        "test_sample_count": len(test_indices),
    }
    artifact = {
        **inference_artifact,
        "model_name": "OneDCNNExerciseClassifier",
        "model_version": model_version,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_names": list(FEATURE_NAMES),
        "classes": classes,
        "supported_sensor_placements": sorted({row["sensor_placement"] for row in rows}),
        "minimum_sampling_rate_hz": 8.0,
        "recommended_sampling_rate_hz": 10.0,
        "status": "EXPERIMENTAL",
        "architecture": {
            "type": "1d_cnn",
            "kernel_size": kernel_size,
            "filter_count": filter_count,
            "activation": "relu",
            "pooling": "global_max",
            "classifier": "dense_softmax",
            "training_epochs": 250,
        },
        "metrics": metrics,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / f"{model_version}.json"
    _write_json(artifact_path, artifact)
    checksum = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    evaluation_path = output_dir / f"{model_version}.evaluation.json"
    _write_json(evaluation_path, metrics)
    return {"artifact_path": str(artifact_path), "evaluation_path": str(evaluation_path), "sha256": checksum, **metrics}


def format_confusion_matrix(metrics: dict[str, Any]) -> str:
    classes = [str(label) for label in metrics["classes"]]
    matrix = metrics["confusion_matrix"]
    if len(matrix) != len(classes) or any(len(row) != len(classes) for row in matrix):
        raise ValueError("Confusion matrix dimensions do not match the model classes.")
    cell_width = max(8, *(len(label) for label in classes))
    corner = "actual / predicted"
    cell_width = max(cell_width, len(corner))
    header = f"{corner:<{cell_width}}" + "".join(
        f"{label:>{cell_width}}" for label in classes
    )
    rows = [
        f"{label:<{cell_width}}" + "".join(f"{int(value):>{cell_width}d}" for value in row)
        for label, row in zip(classes, matrix, strict=True)
    ]
    return "\n".join([header, *rows])


def _dataset_provenance(rows: list[dict[str, str]]) -> str:
    provenances = {row.get("dataset_provenance") or "UNSPECIFIED" for row in rows}
    if len(provenances) != 1:
        raise ValueError("A training dataset cannot mix real, synthetic, or unspecified provenance.")
    return next(iter(provenances))


def _export_tree(model: Any, estimator: Any) -> dict[str, Any]:
    tree = estimator.tree_

    def export(index: int) -> dict[str, Any]:
        if tree.children_left[index] == tree.children_right[index]:
            predicted = str(model.classes_[int(tree.value[index][0].argmax())])
            return {"class": str(predicted)}
        return {
            "feature_index": int(tree.feature[index]),
            "threshold": float(tree.threshold[index]),
            "left": export(int(tree.children_left[index])),
            "right": export(int(tree.children_right[index])),
        }

    return export(0)


def _read_csv(path: Path, required: set[str]) -> list[dict[str, str]]:
    if not path.is_file():
        raise ValueError(f"Required dataset file is missing: {path.name}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            missing = sorted(required - set(reader.fieldnames or []))
            raise ValueError(f"{path.name} is missing required columns: {', '.join(missing)}")
        return list(reader)


def _finite(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be numeric.") from error
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite.")
    return number


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
