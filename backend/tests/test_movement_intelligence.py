import json
import math

import pytest
from pydantic import ValidationError

from app.ml.analysis import (
    AnomalyObservation,
    BaselineStatus,
    FatigueStatus,
    MovementAnomalyEngine,
    PersonalBaseline,
    SignalQualityStatus,
    assess_signal_quality,
    classify_progress,
    compare_baseline,
    fatigue_signal,
)
from app.ml.cnn import OneDCNNJsonModel
from app.ml.features import FEATURE_NAMES, FEATURE_SCHEMA_VERSION, extract_features
from app.ml.forest import RandomForestJsonModel
from app.ml.training import build_feature_rows, format_confusion_matrix, train_1d_cnn, write_feature_rows
from app.schemas.movement import BaselineComparison, MovementIntelligenceInput, SensorQuality


def make_samples(count: int = 31, *, rate_hz: int = 10) -> list[dict[str, float]]:
    return [
        {
            "timestamp": index * 1000 / rate_hz,
            "ax": math.sin(index / 3),
            "ay": 0.1,
            "az": 1.0 + math.cos(index / 3) * 0.1,
            "gx": 0.2 * math.sin(index / 3),
            "gy": 0.03,
            "gz": 0.02,
        }
        for index in range(count)
    ]


def test_feature_schema_has_finite_raw_and_temporal_features() -> None:
    features = extract_features(make_samples())

    assert FEATURE_SCHEMA_VERSION == "movement-features-v1"
    assert tuple(features) == FEATURE_NAMES
    assert len(features) == 45
    assert features["sample_count"] == 31
    assert 9.9 <= features["sampling_rate_hz"] <= 10.1
    assert features["dynamic_acceleration_rms"] > 0
    assert all(math.isfinite(value) for value in features.values())


@pytest.mark.parametrize(
    "samples",
    [
        [],
        [{"timestamp": 1, "ax": 0}],
        make_samples(4)[:3] + [{**make_samples(4)[3], "ax": math.nan}],
    ],
)
def test_feature_extraction_rejects_short_or_nonfinite_windows(samples) -> None:
    with pytest.raises(ValueError):
        extract_features(samples)


def test_signal_quality_marks_low_rate_or_nonincreasing_time_insufficient() -> None:
    low_rate = assess_signal_quality(
        [0, 250, 500, 750, 1000],
        [1.0, 1.1, 1.0, 0.9, 1.0],
    )
    assert low_rate.status == SignalQualityStatus.INSUFFICIENT

    with pytest.raises(ValueError, match="strictly increasing"):
        assess_signal_quality([0, 100, 100], [1.0, 1.0, 1.0])


def test_personal_baseline_requires_session_and_rep_minimums_and_matching_context() -> None:
    assert compare_baseline(
        None,
        exercise_id="squat",
        sensor_placement="THIGH",
        durations_ms=[1000],
        amplitudes=[0.5],
    ) == BaselineStatus.PERSONAL_BASELINE_NOT_AVAILABLE
    under_sampled = PersonalBaseline("squat", "THIGH", 2, 30, 1000, 50, 0.5)
    assert compare_baseline(
        under_sampled,
        exercise_id="squat",
        sensor_placement="THIGH",
        durations_ms=[1000],
        amplitudes=[0.5],
    ) == BaselineStatus.INSUFFICIENT_DATA
    available = PersonalBaseline("squat", "THIGH", 3, 20, 1000, 50, 0.5)
    assert compare_baseline(
        available,
        exercise_id="squat",
        sensor_placement="THIGH",
        durations_ms=[1000, 1010, 990],
        amplitudes=[0.5, 0.49, 0.51],
    ) == BaselineStatus.STABLE
    assert compare_baseline(
        available,
        exercise_id="squat",
        sensor_placement="WAIST",
        durations_ms=[1000],
        amplitudes=[0.5],
    ) == BaselineStatus.INSUFFICIENT_DATA


def test_fatigue_progress_and_repeated_anomaly_need_enough_observations() -> None:
    assert fatigue_signal([1000, 1000, 1000]) == FatigueStatus.INSUFFICIENT_DATA
    assert fatigue_signal([1000, 1000, 1000, 1500, 1600, 1700]) == FatigueStatus.HIGH
    assert classify_progress(["GOOD", "MODERATE"]) == "INSUFFICIENT_DATA"
    assert classify_progress(["MODERATE", "MODERATE", "GOOD", "GOOD"]) == "IMPROVING"
    anomaly = MovementAnomalyEngine(confirmation_count=3)
    assert not anomaly.observe(AnomalyObservation(2.2, 0.2, 1))
    assert not anomaly.observe(AnomalyObservation(2.1, 0.3, 2))
    assert anomaly.observe(AnomalyObservation(2.4, 0.4, 3))


def test_random_forest_json_requires_active_versioned_compatible_model() -> None:
    model = {
        "status": "EXPERIMENTAL",
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "trees": [{"class": "SQUAT"}],
        "classes": ["SQUAT"],
    }
    with pytest.raises(ValueError, match="ACTIVE"):
        RandomForestJsonModel(model, expected_schema=FEATURE_SCHEMA_VERSION)
    with pytest.raises(ValueError, match="schema"):
        RandomForestJsonModel({**model, "status": "ACTIVE"}, expected_schema="movement-features-v2")


def test_1d_cnn_model_artifact_is_active_and_predicts_a_known_label(tmp_path) -> None:
    rows = []
    labels = ["REST", "REST", "REST", "REST", "SQUAT", "SQUAT", "SQUAT", "SQUAT"]
    for athlete_index, label in enumerate(labels, start=1):
        for session_index in range(2):
            feature_values = [0.0] * len(FEATURE_NAMES)
            for position, name in enumerate(FEATURE_NAMES):
                value = 0.2 if "mean" in name else 0.05 if "std" in name else 0.3
                if label == "SQUAT" and "mean" in name and "ax" in name:
                    value = 1.2
                if label == "REST" and "mean" in name and "ax" in name:
                    value = 0.3
                feature_values[position] = value
            rows.append(
                {
                    "athlete_id": f"athlete_{athlete_index:04d}",
                    "session_id": f"athlete_{athlete_index:04d}-session-{session_index}",
                    "exercise": label,
                    "sensor_placement": "THIGH",
                    **{name: value for name, value in zip(FEATURE_NAMES, feature_values)},
                }
            )
    features_path = tmp_path / "movement-features.csv"
    write_feature_rows(rows, features_path)
    simulated_rows = [{**row, "dataset_provenance": "SYNTHETIC_SIMULATION"} for row in rows]
    simulated_features_path = tmp_path / "synthetic-movement-features.csv"
    write_feature_rows(simulated_rows, simulated_features_path)
    with pytest.raises(ValueError, match="explicit allow_synthetic"):
        train_1d_cnn(
            simulated_features_path,
            tmp_path / "models",
            model_version="cnn-synthetic-guard",
        )

    result = train_1d_cnn(features_path, tmp_path / "models", model_version="cnn-exercise-test")
    artifact = json.loads((tmp_path / "models" / "cnn-exercise-test.json").read_text(encoding="utf-8"))
    assert artifact["status"] == "EXPERIMENTAL"
    model = OneDCNNJsonModel(
        {**artifact, "status": "ACTIVE"},
        expected_schema=FEATURE_SCHEMA_VERSION,
    )
    prediction = model.predict(
        [0.3 if "ax_mean" in name else 0.1 for name in FEATURE_NAMES],
        sampling_rate_hz=10.0,
        sensor_placement="THIGH",
        quality_acceptable=True,
    )
    assert result["accuracy"] >= 0.0
    assert artifact["format"] == "vitapulse-1d-cnn-json-v2"
    assert artifact["architecture"]["type"] == "1d_cnn"
    assert artifact["architecture"]["classifier"] == "dense_softmax"
    assert result["dataset_provenance"] == "UNSPECIFIED"
    assert sum(map(sum, result["confusion_matrix"])) == result["test_sample_count"]
    assert "actual / predicted" in format_confusion_matrix(result)
    assert prediction is not None
    assert prediction.label in {"REST", "SQUAT"}


def test_movement_intelligence_requires_model_provenance_without_confidence() -> None:
    with pytest.raises(ValidationError, match="prediction timestamp provenance"):
        MovementIntelligenceInput(
            exercise_recognition_status="RECOGNIZED",
            recognized_exercise="SQUAT",
            prediction_source="MODEL_INFERRED",
            model_name="RandomForestExerciseClassifier",
            model_version="v1",
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            consistency="STABLE",
            sensor_quality_status=SensorQuality.GOOD,
            baseline_status=BaselineComparison.PERSONAL_BASELINE_NOT_AVAILABLE,
            calculation_version="movement-analysis-v1",
        )


def test_dataset_windowing_uses_only_explicit_human_provenance(tmp_path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    samples = make_samples()
    (dataset / "metadata.csv").write_text(
        "athlete_id,session_id,exercise,sensor_placement,device_id,sampling_rate_hz,source\n"
        "athlete_0001,session_0001,SQUAT,THIGH,ESP32-001,10,LIVE_SENSOR\n",
        encoding="utf-8",
    )
    lines = ["session_id,timestamp,ax,ay,az,gx,gy,gz"]
    lines.extend(
        f"session_0001,{sample['timestamp']},{sample['ax']},{sample['ay']},{sample['az']},"
        f"{sample['gx']},{sample['gy']},{sample['gz']}"
        for sample in samples
    )
    (dataset / "samples.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (dataset / "labels.csv").write_text(
        "session_id,start_ms,end_ms,exercise,label_provenance\n"
        "session_0001,0,3000,SQUAT,MANUAL\n",
        encoding="utf-8",
    )

    rows = build_feature_rows(dataset)
    output = tmp_path / "features.csv"
    write_feature_rows(rows, output)

    assert rows
    assert rows[0]["label_provenance"] == "MANUAL"
    assert output.is_file()

    labels = dataset / "labels.csv"
    labels.write_text(
        "session_id,start_ms,end_ms,exercise,label_provenance\n"
        "session_0001,0,3000,SQUAT,RULE_BASED\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="not ground truth"):
        build_feature_rows(dataset)

    low_rate_samples = make_samples(rate_hz=7)
    lines = ["session_id,timestamp,ax,ay,az,gx,gy,gz"]
    lines.extend(
        f"session_0001,{sample['timestamp']},{sample['ax']},{sample['ay']},{sample['az']},"
        f"{sample['gx']},{sample['gy']},{sample['gz']}"
        for sample in low_rate_samples
    )
    (dataset / "samples.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (dataset / "labels.csv").write_text(
        "session_id,start_ms,end_ms,exercise,label_provenance\n"
        "session_0001,0,4286,SQUAT,MANUAL\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="minimum sample and label-coverage"):
        build_feature_rows(dataset)
