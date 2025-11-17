"""
API routes for scheduler management.
"""
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, Query

from src.schemas.ingestion import SyncStatusSchema
from src.core.logging import get_logger
from src.core.exceptions import SchedulerError

logger = get_logger(__name__)

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])

# Global scheduler service instance (will be injected from main app)
_scheduler_service = None


def set_scheduler_service(scheduler_service):
    """
    Set global scheduler service instance.

    Args:
        scheduler_service: SchedulerService instance
    """
    global _scheduler_service
    _scheduler_service = scheduler_service


def get_scheduler_service():
    """
    Get scheduler service instance.

    Returns:
        SchedulerService instance

    Raises:
        HTTPException: If scheduler not initialized
    """
    if _scheduler_service is None:
        raise HTTPException(
            status_code=503,
            detail="Scheduler service not initialized"
        )
    return _scheduler_service


@router.get("/status", response_model=SyncStatusSchema, status_code=200)
async def get_scheduler_status() -> SyncStatusSchema:
    """
    Get scheduler status.

    Returns:
        Sync status schema

    Raises:
        HTTPException: If status retrieval fails
    """
    try:
        scheduler = get_scheduler_service()
        status = scheduler.get_status()
        return status

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to get scheduler status: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/jobs", response_model=List[Dict[str, Any]], status_code=200)
async def list_jobs() -> List[Dict[str, Any]]:
    """
    List all scheduled jobs.

    Returns:
        List of job information

    Raises:
        HTTPException: If listing fails
    """
    try:
        scheduler = get_scheduler_service()
        jobs = scheduler.get_jobs()
        return jobs

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/start", status_code=200)
async def start_scheduler() -> Dict[str, str]:
    """
    Start the scheduler.

    Returns:
        Success message

    Raises:
        HTTPException: If start fails
    """
    try:
        scheduler = get_scheduler_service()

        if scheduler.is_running():
            return {
                "status": "already_running",
                "message": "Scheduler is already running"
            }

        scheduler.start()

        return {
            "status": "success",
            "message": "Scheduler started successfully"
        }

    except HTTPException:
        raise

    except SchedulerError as e:
        logger.error(f"Failed to start scheduler: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

    except Exception as e:
        logger.error(f"Unexpected error starting scheduler: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/stop", status_code=200)
async def stop_scheduler(
    wait: bool = Query(default=True, description="Wait for running jobs to complete")
) -> Dict[str, str]:
    """
    Stop the scheduler.

    Args:
        wait: Wait for running jobs to complete

    Returns:
        Success message

    Raises:
        HTTPException: If stop fails
    """
    try:
        scheduler = get_scheduler_service()

        if not scheduler.is_running():
            return {
                "status": "not_running",
                "message": "Scheduler is not running"
            }

        scheduler.stop(wait=wait)

        return {
            "status": "success",
            "message": "Scheduler stopped successfully"
        }

    except HTTPException:
        raise

    except SchedulerError as e:
        logger.error(f"Failed to stop scheduler: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

    except Exception as e:
        logger.error(f"Unexpected error stopping scheduler: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/jobs/{job_id}/pause", status_code=200)
async def pause_job(job_id: str) -> Dict[str, str]:
    """
    Pause a specific job.

    Args:
        job_id: Job identifier

    Returns:
        Success message

    Raises:
        HTTPException: If pause fails
    """
    try:
        scheduler = get_scheduler_service()
        scheduler.pause_job(job_id)

        return {
            "status": "success",
            "message": f"Job '{job_id}' paused successfully"
        }

    except HTTPException:
        raise

    except SchedulerError as e:
        logger.error(f"Failed to pause job: {e}")
        raise HTTPException(status_code=404, detail=str(e)) from e

    except Exception as e:
        logger.error(f"Unexpected error pausing job: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/jobs/{job_id}/resume", status_code=200)
async def resume_job(job_id: str) -> Dict[str, str]:
    """
    Resume a paused job.

    Args:
        job_id: Job identifier

    Returns:
        Success message

    Raises:
        HTTPException: If resume fails
    """
    try:
        scheduler = get_scheduler_service()
        scheduler.resume_job(job_id)

        return {
            "status": "success",
            "message": f"Job '{job_id}' resumed successfully"
        }

    except HTTPException:
        raise

    except SchedulerError as e:
        logger.error(f"Failed to resume job: {e}")
        raise HTTPException(status_code=404, detail=str(e)) from e

    except Exception as e:
        logger.error(f"Unexpected error resuming job: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.delete("/jobs/{job_id}", status_code=200)
async def remove_job(job_id: str) -> Dict[str, str]:
    """
    Remove a job from scheduler.

    Args:
        job_id: Job identifier

    Returns:
        Success message

    Raises:
        HTTPException: If removal fails
    """
    try:
        scheduler = get_scheduler_service()
        scheduler.remove_job(job_id)

        return {
            "status": "success",
            "message": f"Job '{job_id}' removed successfully"
        }

    except HTTPException:
        raise

    except SchedulerError as e:
        logger.error(f"Failed to remove job: {e}")
        raise HTTPException(status_code=404, detail=str(e)) from e

    except Exception as e:
        logger.error(f"Unexpected error removing job: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/run-ingestion-now", status_code=200)
async def run_ingestion_now() -> Dict[str, str]:
    """
    Manually trigger ingestion job immediately.

    Returns:
        Success message

    Raises:
        HTTPException: If trigger fails
    """
    try:
        scheduler = get_scheduler_service()
        await scheduler.run_ingestion_now()

        return {
            "status": "success",
            "message": "Ingestion job executed successfully"
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to run ingestion: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/run-cleanup-now", status_code=200)
async def run_cleanup_now() -> Dict[str, str]:
    """
    Manually trigger cleanup job immediately.

    Returns:
        Success message

    Raises:
        HTTPException: If trigger fails
    """
    try:
        scheduler = get_scheduler_service()
        await scheduler.run_cleanup_now()

        return {
            "status": "success",
            "message": "Cleanup job executed successfully"
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to run cleanup: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/run-analytics-now", status_code=200)
async def run_analytics_aggregation_now() -> Dict[str, Any]:
    """
    Manually trigger analytics aggregation job immediately.

    Returns:
        Aggregation statistics

    Raises:
        HTTPException: If trigger fails
    """
    try:
        from src.database import db_manager
        from src.services.analytics_aggregation_service import AnalyticsAggregationService

        async with db_manager.session() as session:
            aggregation_service = AnalyticsAggregationService(session=session)
            stats = await aggregation_service.aggregate_last_5_minutes()

        return {
            "status": "success",
            "message": "Analytics aggregation executed successfully",
            "stats": stats
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to run analytics aggregation: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/backfill-analytics", status_code=200)
async def backfill_analytics() -> Dict[str, Any]:
    """
    Backfill analytics for all historical messages.

    This endpoint aggregates all historical messages into 5-minute time slots
    and creates analytics records for the entire history.

    This is a long-running operation that may take several minutes depending
    on the amount of historical data.

    Returns:
        Backfill statistics

    Raises:
        HTTPException: If backfill fails
    """
    try:
        from src.database import db_manager
        from src.services.analytics_aggregation_service import AnalyticsAggregationService

        logger.info("Starting analytics backfill via API endpoint...")

        async with db_manager.session() as session:
            aggregation_service = AnalyticsAggregationService(session=session)
            stats = await aggregation_service.backfill_all_analytics()

        return {
            "status": "success",
            "message": "Analytics backfill completed successfully",
            "stats": stats
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to run analytics backfill: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
