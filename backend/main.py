from fastapi import FastAPI
from api import api_router
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

def main():
    app = FastAPI(Title="OpenStax Video Scenario Generation API")

    app.include_router(api_router, prefix="/api")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"], # Allows your local frontend
        allow_credentials=True,
        allow_methods=["*"],                     # Allows GET, POST, PUT, DELETE, etc.
        allow_headers=["*"],                     # Allows all headers (e.g., Authorization, Content-Type)
    )
        
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        reload=True
    )
    
if __name__ == "__main__":
    main()