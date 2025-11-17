"""
Main FastAPI application for Telegram Data Cleaner.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request
import redis.asyncio as aioredis

from src.config import settings
from src.core.logging import setup_logging, get_logger
from src.database import db_manager
from src.services.scheduler_service import SchedulerService
from src.api.routes.ingestion import router as ingestion_router
from src.api.routes.scheduler import router as scheduler_router, set_scheduler_service
from src.api.routes.dictionary import router as dictionary_router
from src.api.routes.analytics import router as analytics_router
from src.api.routes.sync import router as sync_router

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Global instances
redis_client = None
scheduler_service = None

# Templates
templates = Jinja2Templates(directory="src/templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    # Startup
    logger.info("Starting Telegram Data Cleaner API...")

    # Initialize database
    logger.info("Initializing database...")
    db_manager.init_engine()
    if await db_manager.health_check():
        logger.info("✓ Database connected")
    else:
        logger.error("✗ Database connection failed")
        raise RuntimeError("Database connection failed")

    # Initialize Redis
    global redis_client
    try:
        redis_client = aioredis.from_url(
            settings.redis_url_str,
            decode_responses=False,
        )
        await redis_client.ping()
        logger.info("✓ Redis connected")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}. Continuing without cache.")
        redis_client = None

    # Initialize Scheduler
    global scheduler_service
    try:
        scheduler_service = SchedulerService(
            db_manager=db_manager,
            redis_client=redis_client,
            ingestion_interval_seconds=settings.polling_interval,
            cleanup_hour=2,  # 2 AM
        )
        set_scheduler_service(scheduler_service)

        # Start scheduler
        scheduler_service.start()
        logger.info("✓ Scheduler started")
    except Exception as e:
        logger.error(f"Scheduler initialization failed: {e}")
        scheduler_service = None

    logger.info("="*60)
    logger.info("🚀 Application started successfully!")
    logger.info("="*60)
    logger.info(f"API URL: http://{settings.api_host}:{settings.api_port}")
    logger.info(f"Docs: http://{settings.api_host}:{settings.api_port}/docs")
    logger.info(f"Redoc: http://{settings.api_host}:{settings.api_port}/redoc")
    logger.info("="*60)

    yield

    # Shutdown
    logger.info("Shutting down...")

    # Stop scheduler
    if scheduler_service and scheduler_service.is_running():
        scheduler_service.stop(wait=True)
        logger.info("✓ Scheduler stopped")

    # Close Redis
    if redis_client:
        await redis_client.aclose()
        logger.info("✓ Redis closed")

    # Close database
    await db_manager.close()
    logger.info("✓ Database closed")

    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Telegram Data Cleaner API",
    description="Real-time Telegram channels data analysis and cleaning system",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
try:
    app.mount("/static", StaticFiles(directory="src/static"), name="static")
except RuntimeError:
    logger.warning("Static files directory not found, skipping mount")

# Register routers
app.include_router(ingestion_router, prefix="/api")
app.include_router(scheduler_router, prefix="/api")
app.include_router(dictionary_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(sync_router, prefix="/api")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Main dictionary management page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Full dashboard (advanced)."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/matches", response_class=HTMLResponse)
async def matches(request: Request):
    """Matching results page."""
    return templates.TemplateResponse("matches.html", {"request": request})


@app.get("/analytics", response_class=HTMLResponse)
async def analytics(request: Request):
    """Channel analytics page."""
    return templates.TemplateResponse("analytics.html", {"request": request})


@app.get("/sync", response_class=HTMLResponse)
async def sync_page(request: Request):
    """Smart sync management page."""
    return templates.TemplateResponse("sync.html", {"request": request})


@app.get("/api")
async def api_root():
    """API root endpoint."""
    return {
        "name": "Telegram Data Cleaner API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc",
        "dashboard": "/",
    }


@app.get("/api/health")
async def health_check():
    """
    Overall health check.
    """
    health = {
        "status": "healthy",
        "database": await db_manager.health_check() if db_manager.engine else False,
        "redis": False,
        "scheduler": scheduler_service.is_running() if scheduler_service else False,
    }

    if redis_client:
        try:
            await redis_client.ping()
            health["redis"] = True
        except:
            health["redis"] = False

    # Determine overall status
    if not health["database"]:
        health["status"] = "unhealthy"
    elif not health["redis"] and not health["scheduler"]:
        health["status"] = "degraded"

    return health


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
