from argparse import ArgumentParser
from pathlib import Path

from app.ml.features import FEATURE_SCHEMA_VERSION
from app.ml.training import build_feature_rows, write_feature_rows


def main() -> None:
    parser = ArgumentParser(description="Build versioned features from labeled IMU windows.")
    parser.add_argument("--dataset", type=Path, default=Path("datasets/movement"))
    parser.add_argument("--output", type=Path, default=Path("build/movement-features.csv"))
    args = parser.parse_args()
    rows = build_feature_rows(args.dataset)
    write_feature_rows(rows, args.output)
    print(f"Wrote {len(rows)} {FEATURE_SCHEMA_VERSION} windows to {args.output}.")


if __name__ == "__main__":
    main()
