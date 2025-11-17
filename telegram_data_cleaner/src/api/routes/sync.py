"""
API routes for smart sync management.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import db_manager
from src.services.smart_sync_service import SmartSyncService
from src.core.logging import get_logger
from src.api.routes.ingestion import get_db_session

logger = get_logger(__name__)

router = APIRouter(prefix="/sync", tags=["Smart Sync"])


@router.post("/auto")
async def auto_sync(
    batch_size: int = Query(1000, ge=100, le=5000, description="تعداد پیام در هر batch"),
    max_batches: Optional[int] = Query(None, description="حداکثر تعداد batch در هر جهت"),
    background: bool = Query(False, description="اجرا در background"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Auto Sync: ابتدا پیام‌های جدید، سپس قدیمی‌ها.

    این بهترین روش sync هست که تضمین میکنه هیچ پیام جدیدی از دست نره.

    Args:
        batch_size: تعداد پیام در هر batch (پیشنهاد: 1000)
        max_batches: حداکثر batch در هر جهت (None = همه)
        background: اجرا در background
        session: Database session

    Returns:
        نتیجه sync یا پیام شروع background task
    """
    sync_service = SmartSyncService(session)

    if background:
        background_tasks.add_task(
            sync_service.auto_sync,
            batch_size=batch_size,
            max_batches_per_direction=max_batches
        )
        return {
            "status": "started",
            "message": "Auto sync در background شروع شد"
        }
    else:
        result = await sync_service.auto_sync(
            batch_size=batch_size,
            max_batches_per_direction=max_batches
        )
        return result


@router.post("/forward")
async def sync_forward(
    batch_size: int = Query(1000, ge=100, le=5000),
    max_batches: Optional[int] = Query(None),
    background: bool = Query(False),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Forward Sync: فقط پیام‌های جدید.

    همیشه از offset=0 شروع میکنه تا پیام جدید از دست نره.
    """
    sync_service = SmartSyncService(session)

    if background:
        background_tasks.add_task(
            sync_service.sync_new_messages,
            batch_size=batch_size,
            max_batches=max_batches
        )
        return {
            "status": "started",
            "message": "Forward sync در background شروع شد"
        }
    else:
        result = await sync_service.sync_new_messages(
            batch_size=batch_size,
            max_batches=max_batches
        )
        return result


@router.post("/backward")
async def sync_backward(
    batch_size: int = Query(1000, ge=100, le=5000),
    max_batches: Optional[int] = Query(None),
    background: bool = Query(False),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Backward Sync: فقط پیام‌های قدیمی.

    از offset قبلی ادامه میده.
    """
    sync_service = SmartSyncService(session)

    if background:
        background_tasks.add_task(
            sync_service.sync_historical_messages,
            batch_size=batch_size,
            max_batches=max_batches
        )
        return {
            "status": "started",
            "message": "Backward sync در background شروع شد"
        }
    else:
        result = await sync_service.sync_historical_messages(
            batch_size=batch_size,
            max_batches=max_batches
        )
        return result


@router.get("/status")
async def get_sync_status(
    session: AsyncSession = Depends(get_db_session)
):
    """
    وضعیت sync رو برمیگردونه.

    نشون میده که forward و backward در چه وضعیتی هستن.
    """
    sync_service = SmartSyncService(session)
    status = await sync_service.get_sync_status()
    return status


@router.post("/reset")
async def reset_sync(
    direction: Optional[str] = Query(None, description="forward, backward یا همه"),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Reset کردن وضعیت sync.

    استفاده: وقتی میخوای از اول شروع کنی.
    """
    sync_service = SmartSyncService(session)
    result = await sync_service.reset_sync_state(direction)
    return result
