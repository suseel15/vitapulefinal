from argparse import ArgumentParser
import json
from pathlib import Path

from app.ml.training import format_confusion_matrix


def main() -> None:
    parser = ArgumentParser(description="Display subject-independent movement-model evaluation metrics.")
    parser.add_argument("--evaluation", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.evaluation.read_text(encoding="utf-8"))
    print(json.dumps(report, indent=2, sort_keys=True))
    print("Confusion matrix (rows = actual, columns = predicted):")
    print(format_confusion_matrix(report))
    print("Review per-class recall/F1 and subject split before any manual model approval.")


if __name__ == "__main__":
    main()
