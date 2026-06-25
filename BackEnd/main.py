from fastapi import FastAPI
from api import api_router
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="OpenStax Video Scenario Generation API")

app.include_router(api_router, prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Allows your local frontend
    allow_credentials=True,
    allow_methods=["*"],  # Allows GET, POST, PUT, DELETE, etc.
    allow_headers=["*"],  # Allows all headers (e.g., Authorization, Content-Type)
)


@app.get("/")
def root():
    return {
        "message": "Welcome to the OpenStax Video Scenario Generation API by Team YAMS! Visit /docs for API documentation."
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
