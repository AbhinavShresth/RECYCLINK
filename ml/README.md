# RecycLink ML pipeline

Training/evaluation is separated from the FastAPI runtime. Start with `../docs/ML_PIPELINE.md` for dataset provenance, license caveats, class mappings, reproducible split rules, commands, and API inference behavior.

No datasets, checkpoint, training run, or evaluation metrics are shipped. Do not interpret the app's unavailable classifier as a demo prediction; the UI allows a manual material selection until a real evaluated checkpoint is installed.

From this directory in a Python 3.12 environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest tests
.\.venv\Scripts\python.exe scripts\inspect_dataset.py data\trashnet
.\.venv\Scripts\python.exe scripts\validate_dataset.py data\trashnet --minimum 20
.\.venv\Scripts\python.exe train.py data\trashnet --out artifacts\trashnet-v1 --epochs 12
```

Review the generated dataset audit and actual held-out evaluation report before copying any checkpoint to a configured backend `ML_MODEL_PATH`. Do not redistribute data or weights until their specific licenses and provenance are checked.
