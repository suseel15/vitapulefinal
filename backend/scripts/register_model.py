from argparse import ArgumentParser
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = ArgumentParser(description="Create a local experimental model registry record.")
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=Path("build/model-registry.json"))
    args = parser.parse_args()
    model = json.loads(args.artifact.read_text(encoding="utf-8"))
    checksum = hashlib.sha256(args.artifact.read_bytes()).hexdigest()
    args.registry.parent.mkdir(parents=True, exist_ok=True)
    records = json.loads(args.registry.read_text(encoding="utf-8")) if args.registry.exists() else []
    records = [record for record in records if record.get("model_version") != model["model_version"]]
    records.append({
        "model_name": model["model_name"],
        "model_version": model["model_version"],
        "feature_schema_version": model["feature_schema_version"],
        "training_dataset_version": "UNASSIGNED",
        "metrics": model["metrics"],
        "artifact_path": args.artifact.name,
        "sha256": checksum,
        "status": "EXPERIMENTAL",
        "supported_exercises": model["classes"],
        "sensor_type": "MPU6050",
        "supported_sensor_placements": model["supported_sensor_placements"],
        "minimum_sampling_rate_hz": model["minimum_sampling_rate_hz"],
        "recommended_sampling_rate_hz": model["recommended_sampling_rate_hz"],
    })
    args.registry.write_text(json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Registered the model as EXPERIMENTAL; manual approval is required for activation.")


if __name__ == "__main__":
    main()
