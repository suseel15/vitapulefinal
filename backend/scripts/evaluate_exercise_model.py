from argparse import ArgumentParser
import json
from pathlib import Path


def main() -> None:
    parser = ArgumentParser(description="Display subject-independent Random Forest evaluation metrics.")
    parser.add_argument("--evaluation", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.evaluation.read_text(encoding="utf-8"))
    print(json.dumps(report, indent=2, sort_keys=True))
    print("Review per-class recall/F1 and subject split before any manual model approval.")


if __name__ == "__main__":
    main()
