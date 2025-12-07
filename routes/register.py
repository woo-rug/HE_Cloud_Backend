from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db import SessionLocal
from pydantic import EmailStr, BaseModel
from models import User
import secrets
from argon2.low_level import hash_secret_raw, Type
import base64

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------------------
# 1) 사용자 이메일 확인 및 PK 등록
# ---------------------------

class RegisterEmailRequest(BaseModel):
    email: EmailStr
    pk: str

@router.post("/email")
def register_email(body: RegisterEmailRequest, db: Session = Depends(get_db)):
    # 중복 이메일 있는지 검증
    user = db.query(User).filter(User.email == body.email).first()
    if user:
        raise HTTPException(status_code=400, detail="Email already registered")

    salt = secrets.token_bytes(16)
    email_code = str(secrets.randbelow(1000000)).zfill(6)

    temp_user = User(
        email = str(body.email),
        pk = body.pk,
        salt = base64.b64encode(salt).decode(),
        argon_mem = 65536,
        argon_time = 3,
        argon_parallel = 1,
        status = "unverified",
        email_code = email_code,
    )
    db.add(temp_user)
    db.commit()
    db.refresh(temp_user)

    print("인증번호 : ", email_code)
    return {"message" : "이메일이 발송되었습니다. 인증번호를 입력해주세요."}

# ---------------------------
# 2) 이메일 인증번호 확인
# ---------------------------

class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str

@router.post("/verify")
def verify_email(body: VerifyEmailRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found")
    elif body.code != user.email_code:
        raise HTTPException(status_code=400, detail="이메일 코드가 일치하지 않습니다.")

    # 클라이언트 측으로 KDF 정보 반환
    return {
        "salt" : user.salt,
        "argon_mem": user.argon_mem,
        "argon_time": user.argon_time,
        "argon_parallel": user.argon_parallel
    }

# ---------------------------
# 3) 비밀번호 입력 및 enc(SK) 전송
# ---------------------------

class RegisterCompleteRequest(BaseModel):
    email: EmailStr
    password: str
    enc_sk: str
    enc_mk: str

@router.post("/complete")
def register_complete(body: RegisterCompleteRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    salt = base64.b64decode(user.salt)

    pw_verifier = base64.b64encode(hash_secret_raw(
        body.password.encode(),
        salt,
        user.argon_time,
        user.argon_mem,
        user.argon_parallel,
        32,
        Type.ID
    )).decode()

    user.enc_sk = body.enc_sk
    user.enc_mk = body.enc_mk
    user.pw_verifier = pw_verifier
    user.status = "verified"

    db.commit()

    return {"message" : "회원가입이 성공적으로 완료되었습니다."}