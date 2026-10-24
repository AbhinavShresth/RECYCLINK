"""Lazy, replaceable ML inference interface. Missing weights means unavailable, never a guess."""
import io
from pathlib import Path
from typing import Any

from app.core.config import get_settings


class ModelUnavailable(Exception):
    pass


class WasteClassifier:
    def __init__(self) -> None:
        self.model: Any = None
        self.classes: list[str] = []
        self.version = "unavailable"
        self.device = "cpu"

    @property
    def ready(self) -> bool:
        return self.model is not None

    def load(self) -> None:
        settings = get_settings()
        if not settings.ml_model_path:
            return
        path = Path(settings.ml_model_path)
        if not path.is_file():
            return
        try:
            import torch
            from torch import nn
            from torchvision import models

            self.device = "cuda" if settings.ml_device == "auto" and torch.cuda.is_available() else ("cpu" if settings.ml_device == "auto" else settings.ml_device)
            checkpoint = torch.load(path, map_location=self.device, weights_only=True)
            self.classes = checkpoint["classes"]
            model = models.mobilenet_v3_small(weights=None)
            model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, len(self.classes))
            model.load_state_dict(checkpoint["state_dict"])
            model.eval().to(self.device)
            self.model = model
            self.version = str(checkpoint.get("version", settings.ml_model_version))
        except Exception:
            # Do not log checkpoint contents or expose loader details to callers.
            self.model = None

    def classify(self, raw: bytes, mime: str) -> dict[str, Any]:
        if not self.ready:
            raise ModelUnavailable("No trained model checkpoint is configured")
        import torch
        from PIL import Image, UnidentifiedImageError
        from torchvision import transforms

        if mime not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError("Upload a JPEG, PNG, or WebP image")
        try:
            image = Image.open(io.BytesIO(raw))
            image.verify()
            image = Image.open(io.BytesIO(raw)).convert("RGB")
        except (OSError, UnidentifiedImageError, ValueError):
            raise ValueError("Image file is malformed") from None
        transform = transforms.Compose([
            transforms.Resize(256), transforms.CenterCrop(224), transforms.ToTensor(),
            transforms.Normalize([.485, .456, .406], [.229, .224, .225]),
        ])
        tensor = transform(image).unsqueeze(0).to(self.device)
        with torch.inference_mode():
            scores = torch.softmax(self.model(tensor)[0], dim=0)
            values, indices = scores.topk(min(3, len(self.classes)))
        confidence = float(values[0])
        candidate = self.classes[int(indices[0])]
        threshold = get_settings().ml_min_confidence
        return {
            "predicted_class": candidate if confidence >= threshold else "uncertain",
            "candidate_class": candidate,
            "confidence": confidence,
            "top_predictions": [{"class": self.classes[int(i)], "confidence": float(v)} for v, i in zip(values, indices, strict=False)],
            "needs_confirmation": confidence < threshold,
            "recommended_action": "Please confirm the material and check local collection guidance.",
            "model_version": self.version,
            "confidence_note": "Raw softmax score; not a calibrated probability of correctness.",
        }


classifier = WasteClassifier()
