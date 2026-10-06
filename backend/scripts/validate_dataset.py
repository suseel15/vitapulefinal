from argparse import ArgumentParser
from pathlib import Path

from app.ml.training import build_feature_rows


def main() -> None:
    parser = ArgumentParser(description="Validate the pseudonymous movement dataset.")
    parser.add_argument("--dataset", type=Path, default=Path("datasets/movement"))
    args = parser.parse_args()
    rows = build_feature_rows(args.dataset)
    print(f"Validated {len(rows)} labeled movement windows.")
    print("No model is activated by dataset validation.")


if __name__ == "__main__":
    main()
