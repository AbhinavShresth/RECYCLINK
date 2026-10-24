"""Print mapped class counts and invalid image paths without training."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from train import catalog  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("dataset", type=Path)
args = parser.parse_args()
config, records, invalid, counts = catalog(args.dataset)
print(json.dumps({"mapping_version": config["version"], "images_by_class": counts, "valid_images": len(records), "invalid_images": invalid}, indent=2))
