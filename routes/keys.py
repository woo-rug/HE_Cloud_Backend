from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from db import SessionLocal
from models import User
from dependencies.auth import get_current_user
import os
import aiofiles

router = APIRouter()

UPLOAD_FOLDER = "uploads"

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/keys/upload")
async def upload_eval_keys(
    relin_key: UploadFile = File(...),
    galois_key: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # 1. 저장 경로 설정: uploads/keys/user_{id}/
    user_key_dir = os.path.join(UPLOAD_FOLDER, "keys", f"user_{user.id}")
    os.makedirs(user_key_dir, exist_ok=True)

    print(f"[INFO] 키 업로드 요청 받음: User {user.id}")  # 디버깅용 로그

    # 2. RelinKey 저장
    relin_path = os.path.join(user_key_dir, "relin_keys.k")
    async with aiofiles.open(relin_path, 'wb') as f:
        content = await relin_key.read()
        await f.write(content)

    # 3. GaloisKey 저장
    gal_path = os.path.join(user_key_dir, "gal_keys.k")
    async with aiofiles.open(gal_path, 'wb') as f:
        content = await galois_key.read()
        await f.write(content)

    # 4. DB 상태 업데이트
    user.has_eval_keys = True
    db.commit()

    return {"message": "연산 키(Evaluation Keys) 업로드가 완료되었습니다."}