from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from app.ml.knee_mobility import train_knee_mobility_cnn


def format_confusion_matrix(metrics: dict[str, Any]) -> str:
    classes = metrics["classes"]
    matrix = metrics["confusion_matrix"]
    width = max(8, len("actual / predicted"), *(len(label) for label in classes))
    header = f"{'actual / predicted':<{width}}" + "".join(f"{label:>{width}}" for label in classes)
    rows = [
        f"{label:<{width}}" + "".join(f"{int(value):>{width}d}" for value in row)
        for label, row in zip(classes, matrix, strict=True)
    ]
    return "\n".join([header, *rows])


def main() -> None:
    parser = ArgumentParser(
        description="Train and evaluate an experimental 1D CNN on the supplied knee-mobility dataset."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        required=True,
        help="Folder containing Walking_Data.csv and Climbing_Data.csv.",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("build/knee-mobility"))
    parser.add_argument("--version", default="knee-mobility-1d-cnn-v1")
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()

    result = train_knee_mobility_cnn(
        args.dataset,
        args.output_dir,
        model_version=args.version,
        random_seed=args.seed,
    )
    if result["excluded_malformed_sample_counts"]:
        print(
            "Excluded malformed rows by activity: "
            + ", ".join(
                f"{activity}={count}"
                for activity, count in sorted(result["excluded_malformed_sample_counts"].items())
            )
        )
    print(f"Dataset provenance: {result['dataset_provenance']}")
    print(f"Target: {result['target']}")
    print(f"Participant-independent split: {result['train_subject_count']} train / {result['test_subject_count']} test")
    print(f"Samples: {result['train_sample_count']} train / {result['test_sample_count']} test")
    print(f"Participants with conflicting source labels: {result['participants_with_conflicting_source_labels']}")
    print(f"Holdout accuracy: {result['accuracy']:.3f}")
    print(f"Balanced accuracy: {result['balanced_accuracy']:.3f}")
    print(f"Test-set majority-class baseline: {result['majority_class_baseline_accuracy']:.3f}")
    print(f"Classes: {', '.join(result['classes'])}")
    print("Confusion matrix (rows = actual, columns = predicted):")
    print(format_confusion_matrix(result))
    print(f"Experimental artifact: {result['artifact_path']}")
    print(f"Evaluation: {result['evaluation_path']}")
    print(f"SHA-256: {result['sha256']}")
    print("This dataset-specific artifact is not compatible with the athlete inference API.")


if __name__ == "__main__":
    main()
