from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from utils.token import SECRET_KEY, ALGORITHM
from db import SessionLocal
from models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        email = payload.get("email")

        if user_id is None or email is None:
            raise HTTPException(status_code=401, detail="토큰 페이로드가 유효하지 않습니다.")
    except JWTError:
        raise HTTPException(status_code=401, detail="유효하지 않거나, 만료된 토큰입니다.")

    db = SessionLocal()
    user = db.query(User).filter(User.email == email, User.id == user_id).first()
    db.close()

    if user is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 회원입니다.")
    return user