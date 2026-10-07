import csv

import pytest

from app.ml.knee_mobility import _parse_sequence, train_knee_mobility_cnn


def make_row(label: str, offset: float = 0.0) -> dict[str, str]:
    row = {"Name": "Participant", "label": label}
    for index in range(1, 121):
        row[f"Reading_{index}"] = "|".join(str(offset + channel + index / 100) for channel in range(12))
    return row


def test_parser_requires_exactly_twelve_finite_channels_per_reading() -> None:
    row = make_row("Healthy")
    assert len(_parse_sequence(row)) == 120
    assert all(len(reading) == 12 for reading in _parse_sequence(row))

    row["Reading_20"] = "1|2|3"
    with pytest.raises(ValueError, match="channel count"):
        _parse_sequence(row)


def test_training_evaluation_keeps_participants_grouped_and_excludes_bad_rows(tmp_path) -> None:
    activity_dir = tmp_path / "dataset"
    activity_dir.mkdir()
    headers = ["Name", "Gender", "Age", "BMI", *(f"Reading_{i}" for i in range(1, 121)), "label"]
    labels = ("Bad", "Healthy", "Moderate")
    for filename in ("Walking_Data.csv", "Climbing_Data.csv"):
        with (activity_dir / filename).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            for label_index, label in enumerate(labels):
                for participant_index in range(8):
                    row = make_row(
                        label,
                        offset=float(label_index * 10 + participant_index),
                    )
                    row.update(
                        Name=f"Participant {label_index}-{participant_index}",
                        Gender="not-used",
                        Age="not-used",
                        BMI="not-used",
                    )
                    if filename == "Walking_Data.csv" and label_index == 0 and participant_index == 0:
                        row["Reading_20"] = "malformed"
                    writer.writerow(row)

    result = train_knee_mobility_cnn(activity_dir, tmp_path / "models", random_seed=17)

    assert result["dataset_provenance"] == "USER_PROVIDED_KNEE_SENSOR_DATA"
    assert result["participants_with_conflicting_source_labels"] == 0
    assert result["train_sample_count"] + result["test_sample_count"] == 47
    assert result["train_subject_count"] + result["test_subject_count"] == 24
    assert sum(map(sum, result["confusion_matrix"])) == result["test_sample_count"]
    assert result["excluded_malformed_sample_counts"] == {"Walking_Data.csv": 1}
    assert (tmp_path / "models" / "knee-mobility-1d-cnn-v1.json").is_file()
