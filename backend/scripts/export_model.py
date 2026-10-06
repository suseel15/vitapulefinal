from argparse import ArgumentParser
import hashlib
import json
from pathlib import Path
import shutil

from app.ml.features import FEATURE_NAMES, FEATURE_SCHEMA_VERSION


def main() -> None:
    parser = ArgumentParser(description="Verify and export the safe JSON forest artifact.")
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("build/exported-models"))
    args = parser.parse_args()
    model = json.loads(args.artifact.read_text(encoding="utf-8"))
    if model.get("format") != "vitapulse-random-forest-json-v1":
        raise SystemExit("Unsupported model artifact format.")
    if model.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
        raise SystemExit("Artifact feature schema does not match this exporter.")
    if model.get("feature_names") != list(FEATURE_NAMES):
        raise SystemExit("Artifact feature ordering does not match this exporter.")
    if model.get("status") != "EXPERIMENTAL":
        raise SystemExit("Only an explicitly experimental artifact can be exported by this pipeline.")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    target = args.output_dir / args.artifact.name
    shutil.copyfile(args.artifact, target)
    checksum = hashlib.sha256(target.read_bytes()).hexdigest()
    manifest = {
        "model_name": model["model_name"],
        "model_version": model["model_version"],
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "sha256": checksum,
        "status": "EXPERIMENTAL",
        "artifact": target.name,
    }
    (args.output_dir / f"{target.stem}.manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Exported verified JSON artifact with SHA-256 {checksum}; status remains EXPERIMENTAL.")


if __name__ == "__main__":
    main()
