from argparse import ArgumentParser
from pathlib import Path

from app.ml.training import format_confusion_matrix, train_1d_cnn, train_random_forest


def main() -> None:
    parser = ArgumentParser(description="Train a subject-independent movement model for VitaPulse.")
    parser.add_argument("--features", type=Path, default=Path("build/movement-features.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("build/models"))
    parser.add_argument("--version", default="cnn-exercise-v2")
    parser.add_argument("--model-type", choices=("cnn", "random-forest"), default="cnn")
    parser.add_argument(
        "--allow-synthetic",
        action="store_true",
        help="Allow explicit SYNTHETIC_SIMULATION training data for pipeline testing only.",
    )
    args = parser.parse_args()
    trainer = train_1d_cnn if args.model_type == "cnn" else train_random_forest
    result = trainer(
        args.features,
        args.output_dir,
        model_version=args.version,
        allow_synthetic=args.allow_synthetic,
    )
    if result["dataset_provenance"] == "SYNTHETIC_SIMULATION":
        print("WARNING: SYNTHETIC DATA ONLY - this matrix is not a real-world model evaluation.")
    else:
        print(f"Dataset provenance: {result['dataset_provenance']}")
    print(f"Artifact: {result['artifact_path']}")
    print(f"Subject-independent test accuracy: {result['accuracy']:.3f}")
    print(f"Classes: {', '.join(result['classes'])}")
    print(f"Test samples: {result['test_sample_count']}")
    print("Confusion matrix (rows = actual, columns = predicted):")
    print(format_confusion_matrix(result))
    print(f"Evaluation: {result['evaluation_path']}")
    print(f"SHA-256: {result['sha256']}")
    print("Training output is experimental and is not activated for athlete inference.")


if __name__ == "__main__":
    main()
