from argparse import ArgumentParser
from pathlib import Path

from app.ml.training import train_random_forest


def main() -> None:
    parser = ArgumentParser(description="Train an experimental subject-independent Random Forest.")
    parser.add_argument("--features", type=Path, default=Path("build/movement-features.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("build/models"))
    parser.add_argument("--version", default="rf-exercise-v1")
    args = parser.parse_args()
    result = train_random_forest(args.features, args.output_dir, model_version=args.version)
    print(f"Experimental artifact: {result['artifact_path']}")
    print(f"Subject-independent test accuracy: {result['accuracy']:.3f}")
    print(f"SHA-256: {result['sha256']}")
    print("The artifact remains EXPERIMENTAL and must be separately validated and activated.")


if __name__ == "__main__":
    main()
