"""
API routes module.
"""
from src.api.routes.ingestion import router as ingestion_router
from src.api.routes.scheduler import router as scheduler_router

__all__ = [
    "ingestion_router",
    "scheduler_router",
]
