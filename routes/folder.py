from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import SessionLocal
from models import File, User, Folder
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
# 폴더 조회 / 생성
# ----------------
class FolderSearchRequest(BaseModel):
    folder_id: int


def build_folder_response(folder_id, folders, files):
    return {
        "folder_id": folder_id,
        "child_folders": [{
            "folder_id": folder.id,
            "enc_name": folder.enc_name,
            "created_at": folder.created_at,
        } for folder in folders],
        "files": [{
            "file_id": file.id,
            "cipher_title": file.cipher_title,
            "mime": file.mime,
            "uploaded_at": file.uploaded_at,
        } for file in files],
    }


@router.post("/folder/list")
def folder_lookup(body: FolderSearchRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # folder_id가 0(루트)일 때, DB에서는 parent_id가 NULL인 항목을 찾아야 함
    if body.folder_id == 0:
        # parent_id가 NULL인 폴더 검색
        folders = db.query(Folder).filter(Folder.owner_id == user.id, Folder.parent_id.is_(None)).all()
        # folder_id가 NULL인 파일 검색
        files = db.query(File).filter(File.owner_id == user.id, File.folder_id.is_(None)).all()
        return build_folder_response(body.folder_id, folders, files)
    else:
        # 그 외에는 기존대로 검색
        folders = db.query(Folder).filter(Folder.owner_id == user.id, Folder.parent_id == body.folder_id).all()
        files = db.query(File).filter(File.owner_id == user.id, File.folder_id == body.folder_id).all()
        return build_folder_response(body.folder_id, folders, files)


class FolderCreateRequest(BaseModel):
    enc_title: str
    parent_folder_id: Optional[int] = None


@router.post("/folder/create")
def create_folder(body: FolderCreateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    print("부모 폴더 ID 요청값: " + str(body.parent_folder_id))

    parent_folder_id = None

    if body.parent_folder_id is not None and body.parent_folder_id != 0:
        parent_folder = db.query(Folder).filter(Folder.id == body.parent_folder_id, Folder.owner_id == user.id).first()
        if not parent_folder:
            raise HTTPException(status_code=404, detail="부모 폴더가 존재하지 않습니다.")
        parent_folder_id = body.parent_folder_id

    new_folder = Folder(
        owner_id=user.id,
        parent_id=parent_folder_id,
        enc_name=body.enc_title,
        created_at=datetime.utcnow(),
    )

    db.add(new_folder)
    db.commit()
    db.refresh(new_folder)

    return {
        "folder_id": new_folder.id,
        "parent_id": new_folder.parent_id if new_folder.parent_id is not None else 0,
    }