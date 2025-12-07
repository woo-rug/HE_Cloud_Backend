from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import SessionLocal
from models import Dictionary, User
from dependencies.auth import get_current_user
from datetime import datetime

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------
# 사전 업로드/다운로드
# ----------------

class DictDownloadRequest(BaseModel):
    version: Optional[List[int]] = None

class DictEntry(BaseModel):
    version: int
    enc_vocab: bytes
    scheme: str = "BFV"
    poly_degree: int = 8192
    slot_count: int = 8192
    encoding: str = "BATCH"

class DictDownloadResponse(BaseModel):
    dictionaries: List[DictEntry]

@router.post("/dict/download", response_model=DictDownloadResponse)
def download_dict(body: DictDownloadRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 개인 사전 조회 후 정렬
    query = db.query(Dictionary).filter(Dictionary.owner_id == user.id)

    if body.version:
        query = query.filter(Dictionary.version.in_(body.version))

    results = query.all()
    entries = []
    for result in results:
        entries.append(DictEntry(
            version = result.version,
            enc_vocab = result.enc_vocab,
            scheme = result.scheme,
            poly_degree = result.poly_degree,
            slot_count = result.slot_count,
            encoding = result.encoding,
        ))

    return DictDownloadResponse(dictionaries=entries)

class DictUploadRequest(BaseModel):
    dictionaries: List[DictEntry]

@router.post("/dict/upload")
def upload_dict(body: DictUploadRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    for entry in body.dictionaries:
        dict_row = db.query(Dictionary).filter(Dictionary.owner_id == user.id, Dictionary.version == entry.version).first()

        # 기존 존재 사전 version -> update
        if dict_row:
            dict_row.enc_vocab = entry.enc_vocab
        else:
            new_dict = Dictionary(
                owner_id = user.id,
                version = entry.version,
                enc_vocab = entry.enc_vocab,
                scheme=entry.scheme,
                poly_degree=entry.poly_degree,
                slot_count=entry.slot_count,
                encoding=entry.encoding,
                created_at = datetime.utcnow(),
            )
            db.add(new_dict)

    db.commit()
