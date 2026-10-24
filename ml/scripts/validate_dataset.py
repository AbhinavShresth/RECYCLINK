"""Fail on an empty dataset and report class imbalance explicitly."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from train import catalog  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("dataset", type=Path)
parser.add_argument("--minimum", type=int, default=20)
args = parser.parse_args()
config, records, invalid, counts = catalog(args.dataset)
summary = {"mapping_version": config["version"], "images_by_class": counts, "valid_images": len(records), "invalid_images": len(invalid), "below_minimum": {key: value for key, value in counts.items() if value < args.minimum}, "missing_classes": [key for key, value in counts.items() if value == 0]}
print(json.dumps(summary, indent=2))
if not records:
    raise SystemExit("No valid mapped images found")
