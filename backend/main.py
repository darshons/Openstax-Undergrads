import os
from fastapi import FastAPI
from api import api_router
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import uvicorn

load_dotenv()


app = FastAPI(title="OpenStax Video Scenario Generation API")

app.include_router(api_router, prefix="/api")

# In production the frontend and backend are deployed as one Vercel project
# (backend under the /_/backend prefix), so API calls are same-origin and CORS
# doesn't fire. The list below covers local dev plus any extra origins supplied
# via ALLOWED_ORIGINS (comma-separated) for split deployments / preview URLs.
_default_origins = ["http://localhost:3000"]
_extra_origins = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()
]

app.add_middleware(
        CORSMiddleware,
        allow_origins=_default_origins + _extra_origins,
        allow_credentials=True,
        allow_methods=["*"],                     # Allows GET, POST, DELETE, etc.
        allow_headers=["*"],                     # Allows all headers (e.g. Content-Type)
)

@app.get("/")
def root():
    return {"message": "Welcome to the OpenStax Video Scenario Generation API by Team YAMS! Visit /docs for API documentation."}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)