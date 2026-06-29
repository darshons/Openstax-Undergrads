import os
from fastapi import FastAPI
from api import api_router
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pathlib import Path
import uvicorn

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / "backend.env")

app = FastAPI(title="OpenStax Video Scenario Generation API")

app.include_router(api_router, prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "Welcome to the OpenStax Video Scenario Generation API by Team YAMS! Visit /docs for API documentation."
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
