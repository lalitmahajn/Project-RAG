from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .db.init_db import init_db
from .api.admin import router as admin_router
from .api.scripture import router as scripture_router
from .api.chat import router as chat_router

app = FastAPI(
    title="Scripture Knowledge Base & Research Assistant API",
    description="Backend API for managing, searching, and analyzing religious scriptures using AI.",
    version="1.0.0"
)

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_router)
app.include_router(scripture_router)
app.include_router(chat_router)

@app.on_event("startup")
def startup_event():
    # Make sure DB schema and triggers exist on startup
    init_db()

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "database": "connected",
        "llm_provider": settings.LLM_PROVIDER
    }
