from typing import List
from fastapi import APIRouter, HTTPException, Depends, File, Form, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.responses import FileResponse

from db import SessionLocal
from models import File as FileModel
from models import IndexVector, Dictionary, User, Folder
from dependencies.auth import get_current_user
from datetime import datetime
import os, aiofiles, json, base64

router = APIRouter()

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ----------------
# 파일 업로드/다운로드
# ----------------

class UploadRequest(BaseModel):
    cipher_title: str
    mime: str
    folder_id: int
    dict_version_list: List[int]

    @classmethod
    def as_form(
            cls,
            cipher_title: str = Form(...),
            mime: str = Form("application/octet-stream"),
            folder_id: int = Form(...),
            dict_version_list: str = Form(...),
    ):
        return cls(
            cipher_title=cipher_title,
            mime=mime,
            folder_id=folder_id,
            dict_version_list=json.loads(dict_version_list),
        )


# 파일 + 인덱스 벡터 업로드
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/file/upload")
async def upload_file(
        form: UploadRequest = Depends(UploadRequest.as_form),
        enc_file: UploadFile = File(...),
        index_vectors: List[UploadFile] = File(...),
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
):
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 파일 경로 생성 / 검색
    user_folder = os.path.join(UPLOAD_FOLDER, f"user_{user.id}")
    os.makedirs(user_folder, exist_ok=True)

    # [수정] folder_id가 0(루트)이면 DB에는 NULL(None)로 저장해야 함
    folder_id = form.folder_id if form.folder_id != 0 else None

    file_record = FileModel(
        owner_id=user.id,
        folder_id=folder_id,  # 수정된 변수 사용
        cipher_title=form.cipher_title,
        mime=form.mime,
        uploaded_at=datetime.utcnow(),
        file_path=user_folder,
    )
    db.add(file_record)
    db.commit()
    db.refresh(file_record)  # 파일 고유 아이디값 생성

    # 파일명 확정 및 최종 파일 경로
    file_path = os.path.join(user_folder, f"{file_record.id}.enc")

    # 파일 업로드
    async with aiofiles.open(file_path, mode="wb") as f:
        uploaded_data = await enc_file.read()
        await f.write(uploaded_data)

    # 인덱스
    if len(form.dict_version_list) != len(index_vectors):
        raise HTTPException(status_code=400, detail="사전 정보와 인덱스 벡터 정보가 불일치합니다. 개수 정보 오류")

    for version, index_vector in zip(form.dict_version_list, index_vectors):
        # 인덱스 벡터 저장 경로
        vector_folder = os.path.join(UPLOAD_FOLDER, "index", f"user_{user.id}", f"dict_{version}")
        os.makedirs(vector_folder, exist_ok=True)

        # 해당 사전 정보 찾기
        dict_row = db.query(Dictionary).filter(Dictionary.owner_id == user.id, Dictionary.version == version).first()
        if not dict_row:
            raise HTTPException(status_code=404, detail="사전 정보가 없습니다.")

        index_record = IndexVector(
            owner_id=user.id,
            doc_id=file_record.id,
            dict_id=dict_row.id,
            vector_path=vector_folder,
        )
        db.add(index_record)
        db.commit()
        db.refresh(index_record)

        # 인덱스 벡터명 확정 및 최종 인덱스 벡터 경로
        vector_path = os.path.join(vector_folder, f"{index_record.id}.eiv")  # encrypted index vector

        async with aiofiles.open(vector_path, mode="wb") as f:
            vector_data = await index_vector.read()
            await f.write(vector_data)

    return {"status": "success"}


# 파일 다운로드
class FileDownloadRequest(BaseModel):
    file_id: int


@router.post("/file/download")
def download_file(body: FileDownloadRequest, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    file_row = db.query(FileModel).filter(FileModel.owner_id == user.id, FileModel.id == body.file_id).first()
    if not file_row:
        raise HTTPException(status_code=404, detail="파일에 대한 권한이 없거나, 파일이 존재하지 않습니다.")

    file_path = os.path.join(UPLOAD_FOLDER, f"user_{user.id}", f"{body.file_id}.enc")

    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="파일이 존재하지 않습니다.")

    return FileResponse(
        file_path,
        filename=f"{file_row.cipher_title}",
        media_type=file_row.mime,
    )


# 파일 검색
def build_folder_path(db: Session, folder_id: int, user_id: int):
    path_parts = []

    # folder_id가 0이거나 None이면 바로 루트 반환
    if folder_id == 0 or folder_id is None:
        return [{
            "folder_id": 0,
            "folder_enc_name": None,
        }]

    current = db.query(Folder).filter(Folder.owner_id == user_id, Folder.id == folder_id).first()

    if not current:
        return [{
            "folder_id": 0,
            "folder_enc_name": None,
        }]

    while current:
        path_parts.append({
            "folder_id": current.id,
            "folder_enc_name": current.enc_name,
        })
        if current.parent_id == 0 or current.parent_id is None:
            path_parts.append({
                "folder_id": 0,
                "folder_enc_name": None,
            })
            break
        current = db.query(Folder).filter(Folder.owner_id == user_id, Folder.id == current.parent_id).first()

    path_parts.reverse()
    return path_parts


@router.post("/file/{id}")
def get_file_info(id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    file_row = db.query(FileModel).filter(FileModel.owner_id == user.id, FileModel.id == id).first()
    if not file_row:
        raise HTTPException(status_code=404, detail="파일이 존재하지 않습니다.")

    # folder_id가 None일 수 있으므로 0으로 변환해서 전달하거나 그대로 전달
    folder_id = file_row.folder_id if file_row.folder_id is not None else 0
    paths = build_folder_path(db, folder_id, user.id)

    return {
        "file_id": file_row.id,
        "cipher_title": file_row.cipher_title,
        "mime": file_row.mime,
        "folder_id": folder_id,
        "folder_paths": paths,
        "uploaded_at": file_row.uploaded_at,
    }