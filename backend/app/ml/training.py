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
        if row["source"] != "LIVE_SENSOR":
            raise ValueError(f"Session {session} is not LIVE_SENSOR data.")
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
        if row["label_provenance"] not in ALLOWED_PROVENANCE:
            raise ValueError("Labels must be MANUAL or CLINICIAN_REVIEWED; automatic labels are not ground truth.")
        if row["exercise"] not in ALLOWED_EXERCISES:
            raise ValueError(f"Unsupported labeled exercise class: {row['exercise']}.")
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
                        })
            next_time = start + step_ms
            while cursor < len(ordered) and ordered[cursor]["timestamp"] < next_time:
                cursor += 1
    if not result:
        raise ValueError("No labeled windows met the minimum sample and label-coverage requirements.")
    return result


def write_feature_rows(rows: list[dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["athlete_id", "session_id", "exercise", "sensor_placement", "label_provenance", *FEATURE_NAMES]
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
) -> dict[str, Any]:
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
        from sklearn.model_selection import GroupShuffleSplit
    except ImportError as error:
        raise RuntimeError(
            "Model training requires the optional dependencies; install with pip install -e '.[ml-training]'."
        ) from error

    rows = _read_csv(feature_csv, {"athlete_id", "session_id", "exercise", "sensor_placement", *FEATURE_NAMES})
    subjects = {row["athlete_id"] for row in rows}
    labels = {row["exercise"] for row in rows}
    if len(subjects) < 3 or len(labels) < 2:
        raise ValueError("Training needs at least 3 pseudonymous athletes and 2 exercise classes.")
    features = [[_finite(row[name], name) for name in FEATURE_NAMES] for row in rows]
    targets = [row["exercise"] for row in rows]
    groups = [row["athlete_id"] for row in rows]
    split = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=random_seed)
    train_indices, test_indices = next(split.split(features, targets, groups))
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
    model.fit([features[index] for index in train_indices], [targets[index] for index in train_indices])
    expected = [targets[index] for index in test_indices]
    predicted = model.predict([features[index] for index in test_indices]).tolist()
    classes = sorted(labels)
    metrics = {
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
