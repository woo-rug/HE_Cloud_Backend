from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from utils.token import create_access_token
from db import SessionLocal
from models import User
import base64
from argon2.low_level import hash_secret_raw, Type

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    enc_sk: str
    enc_mk: str
    salt: str
    argon_mem: int
    argon_time: int
    argon_parallel: int
    pk: str

@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User Not Found")
    if user.status != "verified":
        raise HTTPException(status_code=403, detail="User Not Verified")

    salt = base64.b64decode(user.salt)

    calc_verifier = base64.b64encode(hash_secret_raw(
        body.password.encode(),
        salt,
        user.argon_time,
        user.argon_mem,
        user.argon_parallel,
        32,
        Type.ID
    )).decode()

    if calc_verifier != user.pw_verifier:
        raise HTTPException(status_code=401, detail="비밀번호가 일치하지 않습니다.")

    access_token = create_access_token(data={"email": user.email, "user_id": user.id})

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        enc_sk = user.enc_sk,
        enc_mk = user.enc_mk,
        salt = user.salt,
        argon_mem = user.argon_mem,
        argon_parallel = user.argon_parallel,
        argon_time = user.argon_time,
        pk = user.pk,
    )