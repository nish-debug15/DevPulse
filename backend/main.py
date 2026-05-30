from fastapi import FastAPI
import os
from dotenv import load_dotenv

# Import DB components
from db.database import engine, Base
import db.models 

from auth.github_oauth import router as auth_router

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="DevPulse API")
app.include_router(auth_router)

@app.get("/")
def read_root():
    return {"status": "DevPulse backend is alive", "client_id_loaded": bool(os.getenv("GITHUB_CLIENT_ID"))}