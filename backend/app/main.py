"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.routes import router as api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Research platform backend for multimodal adaptive steganography and steganalysis.",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS for frontend access (restricted, non-wildcard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Register API routes under /api
app.include_router(api_router, prefix=settings.API_PREFIX)

@app.get("/", summary="Root Index")
async def root():
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status_url": f"{settings.API_PREFIX}/status",
        "health_url": f"{settings.API_PREFIX}/health",
        "documentation": "/docs"
    }
