from __future__ import annotations

from argparse import ArgumentParser
import csv
import math
from pathlib import Path
import random


EXERCISES = ("REST", "WALK", "SQUAT", "SIT_TO_STAND", "BALANCE")
ATHLETE_COUNT = 12
SAMPLE_RATE_HZ = 10
DURATION_SECONDS = 6


def signal_for(exercise: str, time_seconds: float, variation: float, rng: random.Random) -> dict[str, float]:
    noise = lambda scale: rng.gauss(0.0, scale)
    phase = 2.0 * math.pi
    if exercise == "REST":
        ax = 0.015 * math.sin(phase * 0.2 * time_seconds)
        ay = 0.012 * math.cos(phase * 0.17 * time_seconds)
        az = 1.0 + 0.014 * math.sin(phase * 0.23 * time_seconds)
        gx, gy, gz = 0.008, 0.009, 0.007
    elif exercise == "WALK":
        ax = 0.20 * math.sin(phase * 1.7 * time_seconds)
        ay = 0.08 * math.sin(phase * 0.85 * time_seconds + 0.3)
        az = 1.0 + 0.18 * math.cos(phase * 1.7 * time_seconds)
        gx = 0.22 * math.sin(phase * 1.7 * time_seconds + 0.4)
        gy = 0.08 * math.cos(phase * 0.85 * time_seconds)
        gz = 0.06 * math.sin(phase * 1.2 * time_seconds)
    elif exercise == "SQUAT":
        cycle = phase * 0.62 * time_seconds
        ax = 0.38 * math.sin(cycle) + 0.09 * math.sin(2 * cycle)
        ay = 0.05 * math.sin(cycle + 0.7)
        az = 1.0 + 0.33 * (1.0 - math.cos(cycle))
        gx = 0.40 * math.cos(cycle)
        gy = 0.09 * math.sin(cycle)
        gz = 0.07 * math.cos(cycle * 0.5)
    elif exercise == "SIT_TO_STAND":
        cycle = phase * 0.34 * time_seconds
        ax = 0.47 * math.sin(cycle + 0.15)
        ay = 0.08 * math.sin(cycle * 0.5)
        az = 1.0 + 0.43 * (1.0 - math.cos(cycle))
        gx = 0.30 * math.cos(cycle + 0.15)
        gy = 0.12 * math.sin(cycle)
        gz = 0.05 * math.cos(cycle * 0.5)
    else:
        ax = 0.045 * math.sin(phase * 0.55 * time_seconds)
        ay = 0.035 * math.cos(phase * 0.42 * time_seconds)
        az = 1.0 + 0.035 * math.sin(phase * 0.48 * time_seconds)
        gx = 0.035 * math.sin(phase * 0.5 * time_seconds)
        gy = 0.025 * math.cos(phase * 0.4 * time_seconds)
        gz = 0.02 * math.sin(phase * 0.3 * time_seconds)

    axes = {
        "ax": ax * variation + noise(0.012),
        "ay": ay * variation + noise(0.012),
        "az": 1.0 + (az - 1.0) * variation + noise(0.012),
        "gx": gx * variation + noise(0.015),
        "gy": gy * variation + noise(0.015),
        "gz": gz * variation + noise(0.015),
    }
    return axes


def generate(dataset: Path, *, seed: int = 20261007) -> int:
    dataset.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    metadata_path = dataset / "metadata.csv"
    samples_path = dataset / "samples.csv"
    labels_path = dataset / "labels.csv"
    windows = ATHLETE_COUNT * len(EXERCISES) * 4

    with (
        metadata_path.open("w", newline="", encoding="utf-8") as metadata_handle,
        samples_path.open("w", newline="", encoding="utf-8") as samples_handle,
        labels_path.open("w", newline="", encoding="utf-8") as labels_handle,
    ):
        metadata_writer = csv.DictWriter(
            metadata_handle,
            fieldnames=[
                "athlete_id", "session_id", "exercise", "sensor_placement",
                "device_id", "sampling_rate_hz", "source",
            ],
        )
        sample_writer = csv.DictWriter(
            samples_handle,
            fieldnames=["session_id", "timestamp", "ax", "ay", "az", "gx", "gy", "gz"],
        )
        label_writer = csv.DictWriter(
            labels_handle,
            fieldnames=["session_id", "start_ms", "end_ms", "exercise", "label_provenance"],
        )
        metadata_writer.writeheader()
        sample_writer.writeheader()
        label_writer.writeheader()

        for athlete_index in range(ATHLETE_COUNT):
            athlete_id = f"sim-athlete-{athlete_index + 1:04d}"
            athlete_variation = rng.uniform(0.9, 1.1)
            for exercise_index, exercise in enumerate(EXERCISES):
                session_id = f"sim-sess-{athlete_index + 1:04d}-{exercise_index + 1:02d}"
                metadata_writer.writerow({
                    "athlete_id": athlete_id,
                    "session_id": session_id,
                    "exercise": exercise,
                    "sensor_placement": "THIGH",
                    "device_id": "SIMULATED-IMU-NOT-HARDWARE",
                    "sampling_rate_hz": SAMPLE_RATE_HZ,
                    "source": "SIMULATION",
                })
                label_writer.writerow({
                    "session_id": session_id,
                    "start_ms": 0,
                    "end_ms": DURATION_SECONDS * 1000,
                    "exercise": exercise,
                    "label_provenance": "SYNTHETIC_SIMULATION",
                })
                for sample_index in range(DURATION_SECONDS * SAMPLE_RATE_HZ + 1):
                    timestamp_ms = sample_index * 1000 / SAMPLE_RATE_HZ
                    values = signal_for(
                        exercise,
                        timestamp_ms / 1000,
                        athlete_variation * rng.uniform(0.96, 1.04),
                        rng,
                    )
                    sample_writer.writerow({
                        "session_id": session_id,
                        "timestamp": f"{timestamp_ms:.1f}",
                        **{axis: f"{value:.8f}" for axis, value in values.items()},
                    })

    (dataset / "SYNTHETIC_DATASET_NOTICE.txt").write_text(
        "VITAPULSE SYNTHETIC IMU DATASET\n"
        f"Generator seed: {seed}\n"
        "These are generated numeric signals, not sensor recordings from athletes.\n"
        "Labels are SYNTHETIC_SIMULATION and source is SIMULATION.\n"
        "Use only to test software pipelines. Never describe its metrics as real-world,\n"
        "clinical, safety, or athlete performance. Do not mix with live sensor data.\n",
        encoding="utf-8",
    )
    return windows


def main() -> None:
    parser = ArgumentParser(
        description="Generate deterministic synthetic IMU data for pipeline testing only."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("datasets/movement-synthetic"),
        help="Separate output folder; never overwrite the live movement dataset.",
    )
    parser.add_argument("--seed", type=int, default=20261007)
    args = parser.parse_args()
    if "movement-synthetic" not in args.output.parts:
        parser.error("Synthetic data output must be inside a path component named movement-synthetic.")
    windows = generate(args.output, seed=args.seed)
    print(f"Generated synthetic-only IMU sessions at {args.output}.")
    print(f"Expected eligible windows before feature checks: {windows}.")
    print("NOT LIVE SENSOR DATA. Do not use its metrics as real-world or clinical model performance.")


if __name__ == "__main__":
    main()
