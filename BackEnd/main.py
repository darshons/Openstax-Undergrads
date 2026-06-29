import os
from fastapi import FastAPI
from api import api_router
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import uvicorn

load_dotenv()


app = FastAPI(title="OpenStax Video Scenario Generation API")

app.include_router(api_router, prefix="/api")

# Scenario Studio UI ships as static HTML and is typically served from a local
# static file server (python -m http.server, npx serve, etc.). Cover the common
# local dev ports and allow extras via ALLOWED_ORIGINS (comma-separated).
_default_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8000",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8080",
]
_extra_origins = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()
]

app.add_middleware(
        CORSMiddleware,
        allow_origins=_default_origins + _extra_origins,
        allow_credentials=True,
        allow_methods=["*"],                     # Allows GET, POST, PUT, DELETE, etc.
        allow_headers=["*"],                     # Allows all headers (e.g., Authorization, Content-Type)
)

@app.get("/")
def root():
    return {"message": "Welcome to the OpenStax Video Scenario Generation API by Team YAMS! Visit /docs for API documentation."}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)