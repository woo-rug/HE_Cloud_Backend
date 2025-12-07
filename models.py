from datetime import datetime

from sqlalchemy import Column, String, Integer, Text, ForeignKey, LargeBinary, DateTime, Boolean
# [추가] MySQL의 대용량 데이터 저장을 위한 타입 임포트
from sqlalchemy.dialects.mysql import LONGTEXT, LONGBLOB
from db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True)

    # 동형암호 공개키는 매우 크기 때문에 LONGTEXT 필수
    pk = Column(LONGTEXT)
    enc_sk = Column(LONGTEXT, nullable=True)

    enc_mk = Column(LONGTEXT, nullable=True)  # AES 키는 작아서 Text로 충분
    pw_verifier = Column(Text, nullable=True)
    salt = Column(Text)
    argon_mem = Column(Integer)
    argon_time = Column(Integer)
    argon_parallel = Column(Integer)
    status = Column(String(50))
    email_code = Column(String(10))
    has_eval_keys = Column(Boolean, default=False)


# 유저별 사전 정보
class Dictionary(Base):
    __tablename__ = "dictionaries"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    version = Column(Integer, index=True)

    # [변경] LargeBinary(BLOB, 64KB) -> LONGBLOB(4GB)
    # 사전 데이터가 클 경우를 대비해 LONGBLOB 사용
    enc_vocab = Column(LONGBLOB, nullable=False)

    scheme = Column(String(50))
    poly_degree = Column(Integer)
    slot_count = Column(Integer)
    encoding = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)


# 유저가 올린 문서 정보
class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    cipher_title = Column(LONGTEXT, nullable=False)
    file_path = Column(String(500), nullable=False)  # 경로가 길어질 수 있으므로 넉넉하게
    mime = Column(String(100))
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    folder_id = Column(Integer, ForeignKey("folders.id"), nullable=True)


# 유저가 올린 문서에 대한 인덱스 벡터
class IndexVector(Base):
    __tablename__ = "index_vectors"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    doc_id = Column(Integer, ForeignKey("files.id"), index=True)
    dict_id = Column(Integer, ForeignKey("dictionaries.id"))
    vector_path = Column(LONGTEXT, nullable=False)


class Folder(Base):
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    enc_name = Column(LONGTEXT, nullable=False)
    parent_id = Column(Integer, ForeignKey("folders.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)