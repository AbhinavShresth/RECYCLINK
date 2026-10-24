"""Reproducible MobileNetV3-Small transfer-learning pipeline.

Input layout: dataset_root/<mapped class directory>/*.(jpg|jpeg|png|webp)
Duplicate byte-identical images are grouped before splitting to reduce leakage.
This script reports missing/undersized classes and never fabricates metrics.
"""
import argparse, hashlib, json, random, time
from pathlib import Path
import numpy as np
import torch
from PIL import Image, UnidentifiedImageError
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from torch import nn
from torch.utils.data import Dataset, DataLoader
from torchvision import models, transforms
from src.splitting import stratified_hash_split

SEED=42
LABELS=Path(__file__).with_name('labels.json')
EXTS={'.jpg','.jpeg','.png','.webp'}

def catalog(root):
    cfg=json.loads(LABELS.read_text(encoding='utf-8')); mapping=cfg['dataset_directory_mapping']; classes=cfg['classes']; lookup={d.lower():c for c,dirs in mapping.items() for d in dirs}; records=[]; invalid=[]
    for path in Path(root).rglob('*'):
        if path.suffix.lower() not in EXTS: continue
        label=lookup.get(path.parent.name.lower())
        if not label: continue
        try:
            with Image.open(path) as im: im.verify()
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            records.append({'path':str(path.resolve()),'label':label,'group':digest})
        except (OSError,UnidentifiedImageError) as exc: invalid.append({'path':str(path),'reason':str(exc)})
    group_labels={}
    for row in records: group_labels.setdefault(row['group'],set()).add(row['label'])
    conflicts={digest for digest,labels in group_labels.items() if len(labels)>1}
    if conflicts:
        invalid.extend({'path':row['path'],'reason':'Exact duplicate image has conflicting mapped labels; excluded from training'} for row in records if row['group'] in conflicts)
        records=[row for row in records if row['group'] not in conflicts]
    by_label={c:sum(x['label']==c for x in records) for c in classes}
    return cfg,records,invalid,by_label

def split_groups(records,classes):
    """Per-class deterministic split; duplicate hashes remain in exactly one partition."""
    return tuple(np.asarray(partition, dtype=int) for partition in stratified_hash_split(records, classes, SEED))

class WasteSet(Dataset):
    def __init__(self,rows,classes,training=False):
        self.rows=rows; self.index={c:i for i,c in enumerate(classes)}
        self.tf=transforms.Compose(([transforms.RandomResizedCrop(224,scale=(.75,1)),transforms.RandomHorizontalFlip(),transforms.ColorJitter(.15,.15,.12)] if training else [transforms.Resize(256),transforms.CenterCrop(224)])+[transforms.ToTensor(),transforms.Normalize([.485,.456,.406],[.229,.224,.225])])
    def __len__(self): return len(self.rows)
    def __getitem__(self,i):
        row=self.rows[i]
        with Image.open(row['path']) as im: image=self.tf(im.convert('RGB'))
        return image,self.index[row['label']]

def evaluate(model,loader,device,classes):
    model.eval(); truth=[]; pred=[]; lat=[]
    with torch.inference_mode():
        for x,y in loader:
            x=x.to(device); start=time.perf_counter(); out=model(x); elapsed=(time.perf_counter()-start)*1000/len(x); lat.append(elapsed)
            pred.extend(out.argmax(1).cpu().tolist()); truth.extend(y.tolist())
    return {'test_accuracy':accuracy_score(truth,pred),'per_class':classification_report(truth,pred,labels=list(range(len(classes))),target_names=classes,output_dict=True,zero_division=0),'macro_f1':classification_report(truth,pred,labels=list(range(len(classes))),target_names=classes,output_dict=True,zero_division=0)['macro avg']['f1-score'],'confusion_matrix':confusion_matrix(truth,pred,labels=list(range(len(classes)))).tolist(),'mean_inference_latency_ms_per_image':float(np.mean(lat)) if lat else None}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('dataset',type=Path);ap.add_argument('--out',type=Path,default=Path('checkpoints'));ap.add_argument('--epochs',type=int,default=12);ap.add_argument('--batch-size',type=int,default=32);ap.add_argument('--min-class-images',type=int,default=20);ap.add_argument('--offline-weights',action='store_true',help='Do not request pretrained weights; initialize from torchvision defaults')
    a=ap.parse_args();random.seed(SEED);np.random.seed(SEED);torch.manual_seed(SEED);torch.use_deterministic_algorithms(False);cfg,records,invalid,counts=catalog(a.dataset)
    print(json.dumps({'images_by_class':counts,'invalid_images':len(invalid),'duplicate_image_groups':len(records)-len({x['group'] for x in records})},indent=2))
    if not records: raise SystemExit('No valid images found in mapped class folders.')
    low={k:v for k,v in counts.items() if v<a.min_class_images}
    if low: print('INSUFFICIENT CLASS DATA (reported, not concealed): '+json.dumps(low))
    classes=[c for c in cfg['classes'] if counts[c]>0]
    if not classes: raise SystemExit('No mapped class has images.')
    tr,va,te=split_groups(records,classes)
    split_counts={name:{c:sum(records[int(i)]['label']==c for i in split) for c in classes} for name,split in [('train',tr),('validation',va),('test',te)]}
    artifact_labels={**cfg,'classes':classes,'uncovered_classes':[c for c in cfg['classes'] if c not in classes]}
    a.out.mkdir(parents=True,exist_ok=True); (a.out/'labels.json').write_text(json.dumps(artifact_labels,indent=2),encoding='utf-8')
    (a.out/'dataset_audit.json').write_text(json.dumps({'images_by_class':counts,'split_class_image_counts':split_counts,'invalid_images':invalid,'unique_images':len({x['group'] for x in records}),'missing_classes':[c for c,n in counts.items() if not n],'uncovered_classes':artifact_labels['uncovered_classes']},indent=2),encoding='utf-8')
    device='cuda' if torch.cuda.is_available() else 'cpu'
    loaders=[DataLoader(WasteSet([records[i] for i in split],classes,training=(n==0)),batch_size=a.batch_size,shuffle=(n==0),num_workers=0) for n,split in enumerate((tr,va,te))]
    weights=None if a.offline_weights else models.MobileNet_V3_Small_Weights.DEFAULT
    model=models.mobilenet_v3_small(weights=weights); model.classifier[-1]=nn.Linear(model.classifier[-1].in_features,len(classes)); model.to(device)
    for p in model.features.parameters():p.requires_grad=False
    optimizer=torch.optim.AdamW(model.classifier.parameters(),lr=1e-3,weight_decay=1e-4); lossfn=nn.CrossEntropyLoss(); best=float('inf');patience=3;stale=0; backbone_unfrozen=False
    for epoch in range(a.epochs):
        model.train(); running=0
        for x,y in loaders[0]:
            x,y=x.to(device),y.to(device);optimizer.zero_grad();loss=lossfn(model(x),y);loss.backward();optimizer.step();running+=loss.item()*len(y)
        model.eval(); vl=0; n=0
        with torch.inference_mode():
            for x,y in loaders[1]:x,y=x.to(device),y.to(device);vl+=lossfn(model(x),y).item()*len(y);n+=len(y)
        vl/=max(1,n); print(f'epoch {epoch+1}: train_loss={running/max(1,len(tr)):.4f} validation_loss={vl:.4f}')
        if vl<best:
            best=vl;stale=0;torch.save({'state_dict':model.cpu().state_dict(),'classes':classes,'version':cfg['version'],'input_size':224},a.out/'model.pt');model.to(device)
        else: stale+=1
        if stale>=patience: print('Early stopping.');break
        if not backbone_unfrozen:
            for p in model.features.parameters(): p.requires_grad=True
            optimizer.add_param_group({'params': model.features.parameters(), 'lr': 1e-4, 'weight_decay': 1e-4})
            backbone_unfrozen=True
    saved=torch.load(a.out/'model.pt',map_location=device,weights_only=False);model.load_state_dict(saved['state_dict']);model.to(device)
    report=evaluate(model,loaders[2],device,classes);report.update({'classes':classes,'uncovered_classes':artifact_labels['uncovered_classes'],'class_image_counts':counts,'split_class_image_counts':split_counts,'split_sizes':{'train':len(tr),'validation':len(va),'test':len(te)},'model_version':cfg['version'],'backbone':'MobileNetV3-Small','seed':SEED,'device':device,'pretrained_weights_requested':not a.offline_weights,'threshold_calibration':'not performed; softmax scores are not calibrated probabilities'})
    (a.out/'evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
