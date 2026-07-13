import os
from fastapi import FastAPI
from API.instructor_api import instructor_router
from API.student_api import student_router
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pathlib import Path
import uvicorn

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / "backend.env")

app = FastAPI(title="OpenStax Video Scenario Generation API")

app.include_router(instructor_router, prefix="/instructor_api", tags=["Instructor"])
app.include_router(student_router, prefix="/student_api", tags=["Student"])

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
