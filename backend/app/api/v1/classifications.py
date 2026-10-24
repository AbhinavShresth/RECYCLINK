import hashlib
import json
import warnings
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_csrf
from app.core.config import get_settings
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.models.classification import ClassificationFeedback, WasteClassification
from app.models.identity import User, WasteCategory
from app.services.classifier import ModelUnavailable, classifier

router = APIRouter(prefix="/ai", tags=["waste classification"])


class FeedbackIn(BaseModel):
    prediction_id: UUID
    confirmed_class: str = Field(min_length=2, max_length=32)
    note: str | None = Field(default=None, max_length=500)


@router.get("/status")
def model_status() -> dict:
    if not classifier.ready:
        return {"ready": False, "status": "unavailable", "model_version": None, "message": "A trained checkpoint is not installed. Choose a material manually."}
    return {"ready": True, "status": "ready", "model_version": classifier.version, "device": classifier.device}


@router.post("/classify", status_code=status.HTTP_201_CREATED, dependencies=[Depends(rate_limit("classification", 20, 60))])
async def classify_image(file: UploadFile = File(...), user: User = Depends(get_current_user), _: None = Depends(require_csrf), db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(415, "Upload a JPEG, PNG, or WebP image")
    raw = await file.read(settings.image_upload_max_mb * 1024 * 1024 + 1)
    if not raw:
        raise HTTPException(400, "Image file is empty")
    if len(raw) > settings.image_upload_max_mb * 1024 * 1024:
        raise HTTPException(413, f"Image exceeds {settings.image_upload_max_mb} MB limit")
    try:
        from PIL import Image
        formats = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(__import__("io").BytesIO(raw))
            if image.format != formats[file.content_type]:
                raise ValueError("Image content does not match its declared file type")
            if image.width * image.height > 20_000_000:
                raise ValueError("Image dimensions exceed the 20 megapixel limit")
            image.verify()
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except Exception:
        raise HTTPException(400, "Image file is malformed or exceeds safe dimensions") from None
    if not classifier.ready:
        raise HTTPException(503, "Image classification is unavailable: no trained model checkpoint is installed. You can select a category manually.")
    try:
        result = classifier.classify(raw, file.content_type)
    except ModelUnavailable:
        raise HTTPException(503, "Image classification is temporarily unavailable") from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    prediction_id = uuid4()
    record = WasteClassification(
        id=prediction_id, user_id=user.id, image_sha256=hashlib.sha256(raw).hexdigest(),
        predicted_class=result["predicted_class"], candidate_class=result["candidate_class"],
        confidence=result["confidence"], top_predictions_json=json.dumps(result["top_predictions"]),
        needs_confirmation=result["needs_confirmation"], model_version=result["model_version"],
    )
    db.add(record)
    db.commit()
    return {"prediction_id": str(prediction_id), **result}


@router.post("/feedback", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)])
def classification_feedback(payload: FeedbackIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    category = db.get(WasteCategory, payload.confirmed_class)
    record = db.scalar(select(WasteClassification).where(WasteClassification.id == payload.prediction_id, WasteClassification.user_id == user.id))
    if not category or not category.is_active:
        raise HTTPException(422, "Choose an available material category")
    if record is None:
        raise HTTPException(404, "Classification not found")
    existing = db.scalar(select(ClassificationFeedback.id).where(ClassificationFeedback.classification_id == record.id, ClassificationFeedback.user_id == user.id))
    if existing:
        raise HTTPException(409, "Feedback has already been recorded")
    db.add(ClassificationFeedback(classification_id=record.id, user_id=user.id, confirmed_class=payload.confirmed_class, note=payload.note))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Feedback has already been recorded") from None
    return {"recorded": True, "prediction_id": str(record.id), "confirmed_class": payload.confirmed_class, "retraining": False}


@router.get("/history")
def classification_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    records = db.scalars(select(WasteClassification).where(WasteClassification.user_id == user.id).order_by(WasteClassification.created_at.desc()).limit(100)).all()
    return [{"prediction_id": str(r.id), "predicted_class": r.predicted_class, "candidate_class": r.candidate_class, "confidence": r.confidence, "top_predictions": json.loads(r.top_predictions_json), "needs_confirmation": r.needs_confirmation, "model_version": r.model_version, "created_at": r.created_at.isoformat()} for r in records]
