"""Pydantic schemas for API request and response validation."""
from datetime import datetime, timezone
from typing import Dict, List, Literal
from pydantic import BaseModel, Field

class HealthResponse(BaseModel):
    """Safe health check response containing no sensitive system information."""
    status: Literal["healthy", "degraded", "unhealthy"] = "healthy"
    version: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ModuleStatus(BaseModel):
    """Actual progress status of a specific engineering module."""
    name: str
    phase: int
    status: Literal["implemented", "in_progress", "pending"]
    description: str
    capabilities: List[str] = Field(default_factory=list)

class SystemStatusResponse(BaseModel):
    """Overview of project implementation status across development phases."""
    project_name: str
    version: str
    current_phase: int
    modules: Dict[str, ModuleStatus]
