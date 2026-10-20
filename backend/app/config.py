"""Application configuration settings."""
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Adaptive Multimodal Steganography Platform"
    VERSION: str = "0.1.0"
    API_PREFIX: str = "/api"
    DEBUG: bool = False
    
    # Controlled CORS: Vite dev server by default
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]
    
    # Upload limits (bytes)
    MAX_UPLOAD_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB safety limit

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
