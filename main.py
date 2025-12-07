from fastapi import FastAPI
from routes.register import router as register_router
from routes.login import router as login_router
from routes.folder import router as folder_router
from routes.file import router as file_router
from routes.delete import router as delete_router
from routes.search import router as search_router
from routes.dictionary import router as dict_router
from routes.keys import router as keys_router

from db import engine
from models import Base

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(register_router, prefix="/api/register")
app.include_router(login_router, prefix="/api/auth")
app.include_router(folder_router, prefix="/api")
app.include_router(file_router, prefix="/api")
app.include_router(delete_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(dict_router, prefix="/api")
app.include_router(keys_router, prefix="/api")