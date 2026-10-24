"""Optional local inference API. Run: uvicorn inference:app --port 4180"""
import io, json, os
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel
from PIL import Image, UnidentifiedImageError
import torch
from torch import nn
from torchvision import models, transforms

app=FastAPI(title='RecycLink local image inference',version='1.0')
MODEL=Path(os.getenv('RECYCLINK_MODEL','checkpoints/model.pt'))
THRESHOLD=float(os.getenv('CLASSIFICATION_THRESHOLD','.55'))
MAX_BYTES=8*1024*1024
device='cuda' if torch.cuda.is_available() else 'cpu'
classes=[]; model=None; model_version=None
preprocess=transforms.Compose([transforms.Resize(256),transforms.CenterCrop(224),transforms.ToTensor(),transforms.Normalize([.485,.456,.406],[.229,.224,.225])])

@app.on_event('startup')
def load_model():
    global classes,model,model_version
    if not MODEL.exists(): return
    ckpt=torch.load(MODEL,map_location=device,weights_only=False);classes=ckpt['classes'];model_version=ckpt.get('version','unknown');model=models.mobilenet_v3_small(weights=None);model.classifier[-1]=nn.Linear(model.classifier[-1].in_features,len(classes));model.load_state_dict(ckpt['state_dict']);model.eval().to(device)

@app.get('/health')
def health(): return {'ready':model is not None,'model_version':model_version,'device':device}

@app.post('/api/v1/ai/classify')
async def classify(file:UploadFile=File(...)):
    return predict(await file.read(MAX_BYTES+1),file.content_type)

class ImagePayload(BaseModel):
    image_base64:str
    image_mime:str

@app.post('/api/v1/ai/classify-json')
def classify_json(payload:ImagePayload):
    import base64, binascii
    try: raw=base64.b64decode(payload.image_base64,validate=True)
    except (ValueError,binascii.Error): raise HTTPException(400,'Malformed base64 image')
    return predict(raw,payload.image_mime)

def predict(raw,mime):
    if model is None: raise HTTPException(503,'No trained model checkpoint is installed')
    if mime not in {'image/jpeg','image/png','image/webp'}: raise HTTPException(415,'Upload a JPEG, PNG, or WebP image')
    if len(raw)>MAX_BYTES: raise HTTPException(413,'Image exceeds 8 MB limit')
    try:
        image=Image.open(io.BytesIO(raw)).convert('RGB'); x=preprocess(image).unsqueeze(0).to(device)
    except (OSError,UnidentifiedImageError): raise HTTPException(400,'Image file is malformed')
    with torch.inference_mode(): scores=torch.softmax(model(x)[0],dim=0); vals,idx=scores.topk(min(3,len(classes)))
    confidence=float(vals[0]); category=classes[int(idx[0])]; uncertain=confidence<THRESHOLD
    return {'predicted_class':'uncertain' if uncertain else category,'candidate_class':category,'confidence':confidence,'top_predictions':[{'class':classes[int(i)],'confidence':float(v)} for v,i in zip(vals,idx)],'needs_confirmation':uncertain,'recommended_action':'Please confirm the material and check local collection guidance.','model_version':model_version,'confidence_note':'Raw softmax score; not calibrated probability of correctness.'}
