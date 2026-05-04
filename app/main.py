from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.core.config import settings
from app.routers import categories, cvs, search, emails

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CV Management Service",
    description="Microservice for managing CVs, categories, and candidate search",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(categories.router, prefix="/categories", tags=["categories"])
app.include_router(cvs.router, prefix="/cvs", tags=["cvs"])
app.include_router(search.router, prefix="/search", tags=["search"])
app.include_router(emails.router, prefix="/emails", tags=["emails"])

@app.get("/")
async def root():
    return {"message": "CV Management Service API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}