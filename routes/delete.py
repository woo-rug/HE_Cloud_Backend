from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import SessionLocal
from models import File, IndexVector, User, Folder
from dependencies.auth import get_current_user
import os

router = APIRouter()

# [주의] Docker 환경 변수나 설정에 맞춰 경로 확인 필요
# 로컬인 경우 "uploads", Docker인 경우 "/app/uploads" 등
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
# ----------------
# 파일 / 폴더 삭제
# ----------------

class DeleteRequest(BaseModel):
    type: str
    id: int


# 공통 삭제 함수: 인덱스 파일(.eiv)과 원본 파일(.enc)을 모두 물리적으로 삭제하고 DB도 정리
def delete_file_and_index(db: Session, user_id: int, file_id: int):
    # 1. 삭제할 인덱스 벡터 조회 (물리 파일 삭제를 위해)
    index_vectors = db.query(IndexVector).filter(IndexVector.doc_id == file_id).all()

    # 2. 물리적 인덱스 파일 삭제
    for idx in index_vectors:
        # 저장 경로 규칙: vector_path/{id}.eiv
        idx_file_path = os.path.join(idx.vector_path, f"{idx.id}.eiv")
        if os.path.exists(idx_file_path):
            try:
                os.remove(idx_file_path)
            except OSError:
                pass  # 파일이 없거나 지울 수 없으면 패스

    # [핵심 수정] 3. DB에서 인덱스 벡터 '즉시' 삭제 (Bulk Delete)
    # 이렇게 해야 파일 삭제 시점에 외래키 걸림돌이 사라집니다.
    db.query(IndexVector).filter(IndexVector.doc_id == file_id).delete(synchronize_session=False)

    # 4. 실제 암호화 파일 삭제 (물리 파일)
    file_path = os.path.join(UPLOAD_FOLDER, f"user_{user_id}", f"{file_id}.enc")
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass

    # 5. 파일 DB 삭제
    db.query(File).filter(File.owner_id == user_id, File.id == file_id).delete(synchronize_session=False)


def delete_folder_recursive(db: Session, user_id: int, folder_id: int):
    # 현재 폴더 확인
    folder = db.query(Folder).filter(Folder.owner_id == user_id, Folder.id == folder_id).first()
    if not folder:
        # 이미 삭제되었거나 없으면 스킵
        return

    # 1. 현재 폴더 내의 모든 파일 삭제
    file_ids = find_all_files_id(db, user_id=user_id, folder_id=folder_id)
    for file_id in file_ids:
        delete_file_and_index(db, user_id, file_id)

    # 2. 자식 폴더 확인 -> 재귀 실행
    child_folders_ids = find_all_child_folders_id(db, user_id=user_id, parent_folder_id=folder_id)
    for child_folder_id in child_folders_ids:
        delete_folder_recursive(db, user_id=user_id, folder_id=child_folder_id)

    # 3. 현재 폴더 DB 삭제
    db.query(Folder).filter(Folder.owner_id == user_id, Folder.id == folder_id).delete(synchronize_session=False)
    # 재귀 호출 중에는 commit을 하지 않고, 최상위 호출에서 한 번만 commit 하도록 설계되어 있음
    # (아래 delete_item에서 commit 호출)


def find_all_child_folders_id(db: Session, user_id: int, parent_folder_id: int):
    child_folders = db.query(Folder).filter(Folder.owner_id == user_id, Folder.parent_id == parent_folder_id).all()
    return [folder.id for folder in child_folders]


def find_all_files_id(db: Session, user_id: int, folder_id: int):
    files = db.query(File).filter(File.owner_id == user_id, File.folder_id == folder_id).all()
    return [file.id for file in files]


@router.post("/delete")
def delete_item(body: DeleteRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.type == "file":
        file_row = db.query(File).filter(File.id == body.id, File.owner_id == user.id).first()
        if not file_row:
            raise HTTPException(status_code=404, detail="파일이 존재하지 않습니다.")

        # 공통 함수를 사용하여 인덱스 파일 삭제
        delete_file_and_index(db, user.id, file_row.id)

        db.commit()
        return {"message": "파일 삭제가 완료되었습니다."}

    elif body.type == "folder":
        folder_row = db.query(Folder).filter(Folder.owner_id == user.id, Folder.id == body.id).first()

        if not folder_row:
            raise HTTPException(status_code=404, detail="폴더가 존재하지 않습니다.")

        delete_folder_recursive(db, user_id=user.id, folder_id=folder_row.id)

        db.commit()
        return {"message": "폴더 삭제가 완료되었습니다."}

    else:
        raise HTTPException(status_code=400, detail="파일 또는 폴더가 아닌 다른 값은 불가합니다.")