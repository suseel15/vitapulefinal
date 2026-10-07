from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ACTIVITY_FILES = ("Walking_Data.csv", "Climbing_Data.csv")
MOBILITY_CLASSES = ("Bad", "Healthy", "Moderate")
READING_COUNT = 120
CHANNEL_COUNT = 12


def train_knee_mobility_cnn(
    dataset_dir: Path,
    output_dir: Path,
    *,
    model_version: str = "knee-mobility-1d-cnn-v1",
    random_seed: int = 17,
) -> dict[str, Any]:
    try:
        import numpy as np
        from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report, confusion_matrix
        from sklearn.model_selection import GroupShuffleSplit
    except ImportError as error:
        raise RuntimeError(
            "Model training requires the optional dependencies; install with pip install -e '.[ml-training]'."
        ) from error

    samples: list[list[list[float]]] = []
    targets: list[str] = []
    groups: list[str] = []
    invalid_by_activity: Counter[str] = Counter()
    source_rows: Counter[str] = Counter()
    valid_by_activity: Counter[str] = Counter()

    for filename in ACTIVITY_FILES:
        path = dataset_dir / filename
        if not path.is_file():
            raise ValueError(f"Required knee-mobility source file is missing: {filename}")
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            required = {"Name", "label", *(f"Reading_{index}" for index in range(1, READING_COUNT + 1))}
            if reader.fieldnames is None or not required.issubset(reader.fieldnames):
                missing = sorted(required - set(reader.fieldnames or []))
                raise ValueError(f"{filename} is missing required columns: {', '.join(missing)}")

            seen_subjects: set[str] = set()
            for row in reader:
                source_rows[filename] += 1
                subject = (row.get("Name") or "").strip()
                label = (row.get("label") or "").strip()
                if not subject:
                    raise ValueError(f"{filename} contains a row without a participant identifier.")
                if label not in MOBILITY_CLASSES:
                    raise ValueError(f"{filename} contains an unsupported mobility label.")
                if subject in seen_subjects:
                    raise ValueError(f"{filename} contains more than one row for a participant.")
                seen_subjects.add(subject)

                try:
                    sequence = _parse_sequence(row)
                except ValueError:
                    invalid_by_activity[filename] += 1
                    continue

                samples.append(sequence)
                targets.append(label)
                groups.append(subject)
                valid_by_activity[filename] += 1

    if not samples:
        raise ValueError("No valid knee-mobility samples were found in the source files.")
    if set(targets) != set(MOBILITY_CLASSES):
        raise ValueError("Valid source rows must include Bad, Healthy, and Moderate labels.")

    label_sets_by_subject: dict[str, set[str]] = defaultdict(set)
    for subject, label in zip(groups, targets, strict=True):
        label_sets_by_subject[subject].add(label)
    conflicting_subject_count = sum(len(labels) > 1 for labels in label_sets_by_subject.values())

    feature_values = np.asarray(samples, dtype=np.float64)
    group_values = np.asarray(groups)
    split = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=random_seed)
    train_indices, test_indices = next(split.split(feature_values, targets, group_values))
    train_subjects = set(group_values[train_indices])
    test_subjects = set(group_values[test_indices])
    if train_subjects & test_subjects:
        raise RuntimeError("Participant-independent split invariant failed.")
    train_labels = {targets[index] for index in train_indices}
    test_labels = {targets[index] for index in test_indices}
    if train_labels != set(MOBILITY_CLASSES) or test_labels != set(MOBILITY_CLASSES):
        raise ValueError(
            "The participant-independent split must contain every mobility class on both sides; "
            "collect more labeled participants."
        )

    classes = list(MOBILITY_CLASSES)
    class_to_index = {label: index for index, label in enumerate(classes)}
    train_values = feature_values[train_indices]
    test_values = feature_values[test_indices]
    train_targets = np.asarray([class_to_index[targets[index]] for index in train_indices], dtype=np.int64)

    train_mean = train_values.mean(axis=(0, 1))
    train_scale = train_values.std(axis=(0, 1))
    train_scale[train_scale < 1e-8] = 1.0
    train_values = (train_values - train_mean[None, None, :]) / train_scale[None, None, :]
    test_values = (test_values - train_mean[None, None, :]) / train_scale[None, None, :]

    filter_count = 8
    kernel_size = 5
    rng = np.random.default_rng(random_seed)
    kernels = rng.normal(
        0.0,
        math.sqrt(2.0 / (kernel_size * CHANNEL_COUNT)),
        size=(kernel_size, CHANNEL_COUNT, filter_count),
    )
    convolution_biases = np.zeros(filter_count, dtype=np.float64)
    dense_weights = rng.normal(
        0.0,
        math.sqrt(2.0 / (filter_count + len(classes))),
        size=(filter_count, len(classes)),
    )
    dense_biases = np.zeros(len(classes), dtype=np.float64)

    windows = np.lib.stride_tricks.sliding_window_view(train_values, kernel_size, axis=1)
    windows = np.moveaxis(windows, -1, 2)
    row_indices = np.arange(len(train_targets))[:, None]
    filter_indices = np.arange(filter_count)[None, :]
    for _ in range(250):
        convolution = np.einsum("ntkc,kcf->ntf", windows, kernels) + convolution_biases
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
        winning_activation = activations[row_indices, max_positions, filter_indices]
        activation_gradient[row_indices, max_positions, filter_indices] = (
            pooled_gradient * (winning_activation > 0.0)
        )
        kernel_gradient = np.einsum("ntkc,ntf->kcf", windows, activation_gradient)
        convolution_bias_gradient = activation_gradient.sum(axis=(0, 1))

        learning_rate = 0.03
        dense_weights -= learning_rate * dense_gradient
        dense_biases -= learning_rate * dense_bias_gradient
        kernels -= learning_rate * kernel_gradient
        convolution_biases -= learning_rate * convolution_bias_gradient

    predicted_indices = _predict(
        test_values,
        kernels,
        convolution_biases,
        dense_weights,
        dense_biases,
    )
    expected = [targets[index] for index in test_indices]
    predicted = [classes[index] for index in predicted_indices]

    metrics = {
        "dataset_provenance": "USER_PROVIDED_KNEE_SENSOR_DATA",
        "target": "source-provided mobility label (Bad, Healthy, Moderate)",
        "source_files": list(ACTIVITY_FILES),
        "input_shape_per_sample": [READING_COUNT, CHANNEL_COUNT],
        "accuracy": float(accuracy_score(expected, predicted)),
        "balanced_accuracy": float(balanced_accuracy_score(expected, predicted)),
        "majority_class_baseline_accuracy": max(Counter(expected).values()) / len(expected),
        "classification_report": classification_report(
            expected,
            predicted,
            labels=classes,
            output_dict=True,
            zero_division=0,
        ),
        "confusion_matrix": confusion_matrix(expected, predicted, labels=classes).tolist(),
        "classes": classes,
        "train_subject_count": len(train_subjects),
        "test_subject_count": len(test_subjects),
        "train_sample_count": len(train_indices),
        "test_sample_count": len(test_indices),
        "train_class_counts": dict(Counter(targets[index] for index in train_indices)),
        "test_class_counts": dict(Counter(expected)),
        "source_row_counts": dict(source_rows),
        "valid_sample_counts": dict(valid_by_activity),
        "excluded_malformed_sample_counts": dict(invalid_by_activity),
        "participants_with_conflicting_source_labels": conflicting_subject_count,
        "random_seed": random_seed,
        "model_status": "EXPERIMENTAL",
    }
    artifact = {
        "format": "vitapulse-knee-mobility-1d-cnn-v1",
        "model_name": "KneeMobilityOneDCNN",
        "model_version": model_version,
        "status": "EXPERIMENTAL",
        "serving_compatible": False,
        "source_dataset": "user-provided Walking_Data.csv and Climbing_Data.csv",
        "input_shape": [READING_COUNT, CHANNEL_COUNT],
        "input_channel_semantics": "Undocumented source-provided sensor channels; order preserved.",
        "classes": classes,
        "normalization_mean": train_mean.tolist(),
        "normalization_scale": train_scale.tolist(),
        "conv_kernels": kernels.tolist(),
        "conv_biases": convolution_biases.tolist(),
        "dense_weights": dense_weights.tolist(),
        "dense_biases": dense_biases.tolist(),
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
    evaluation_path = output_dir / f"{model_version}.evaluation.json"
    _write_json(artifact_path, artifact)
    _write_json(evaluation_path, metrics)
    return {
        "artifact_path": str(artifact_path),
        "evaluation_path": str(evaluation_path),
        "sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
        **metrics,
    }


def _parse_sequence(row: dict[str, str]) -> list[list[float]]:
    sequence: list[list[float]] = []
    for index in range(1, READING_COUNT + 1):
        values = (row.get(f"Reading_{index}") or "").split("|")
        if len(values) != CHANNEL_COUNT:
            raise ValueError("A reading does not contain the expected channel count.")
        try:
            reading = [float(value) for value in values]
        except ValueError as error:
            raise ValueError("A reading contains a nonnumeric channel.") from error
        if not all(math.isfinite(value) for value in reading):
            raise ValueError("A reading contains a non-finite channel.")
        sequence.append(reading)
    return sequence


def _predict(
    values: Any,
    kernels: Any,
    convolution_biases: Any,
    dense_weights: Any,
    dense_biases: Any,
) -> list[int]:
    import numpy as np

    windows = np.lib.stride_tricks.sliding_window_view(values, kernels.shape[0], axis=1)
    windows = np.moveaxis(windows, -1, 2)
    convolution = np.einsum("ntkc,kcf->ntf", windows, kernels) + convolution_biases
    pooled = np.maximum(convolution, 0.0).max(axis=1)
    logits = pooled @ dense_weights + dense_biases
    return logits.argmax(axis=1).tolist()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
