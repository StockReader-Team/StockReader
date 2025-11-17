"""
Scheduler service for periodic ingestion and cleanup tasks.
"""
import asyncio
from datetime import datetime
from typing import Optional, Callable, Dict, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

import redis.asyncio as aioredis

from src.config import settings
from src.core.logging import get_logger
from src.core.exceptions import SchedulerError, JobExecutionError
from src.services.ingestion_service import IngestionService
from src.core.analytics.channel_analytics_service import ChannelAnalyticsService
from src.services.analytics_aggregation_service import AnalyticsAggregationService
from src.database import DatabaseManager
from src.schemas.ingestion import SyncStatusSchema

logger = get_logger(__name__)


class SchedulerService:
    """
    Manages periodic tasks for data ingestion and cleanup.

    Features:
    - Periodic ingestion job (every 3-4 minutes)
    - Daily cleanup job (remove old messages)
    - Job monitoring and error handling
    - Graceful start/stop
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        redis_client: Optional[aioredis.Redis] = None,
        ingestion_interval_seconds: Optional[int] = None,
        cleanup_hour: int = 2,  # Run cleanup at 2 AM
    ):
        """
        Initialize scheduler service.

        Args:
            db_manager: Database manager instance
            redis_client: Redis client for caching (optional)
            ingestion_interval_seconds: Ingestion interval (default: from settings)
            cleanup_hour: Hour of day for cleanup (default: 2 AM)
        """
        self.db_manager = db_manager
        self.redis_client = redis_client
        self.ingestion_interval = ingestion_interval_seconds or settings.polling_interval
        self.cleanup_hour = cleanup_hour

        # Initialize scheduler
        self.scheduler = AsyncIOScheduler()
        self.scheduler.add_listener(
            self._job_executed_listener,
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
        )

        # Status tracking
        self.sync_status = SyncStatusSchema(is_running=False)
        self._is_running = False

        logger.info(
            f"SchedulerService initialized "
            f"(ingestion_interval={self.ingestion_interval}s, "
            f"cleanup_hour={self.cleanup_hour})"
        )

    def _job_executed_listener(self, event):
        """
        Listen to job execution events.

        Args:
            event: APScheduler event
        """
        if event.exception:
            logger.error(
                f"Job '{event.job_id}' failed with exception: {event.exception}"
            )
            self.sync_status.last_error = str(event.exception)
        else:
            logger.info(f"Job '{event.job_id}' executed successfully")

    async def _ingestion_job(self) -> None:
        """
        Periodic ingestion job.

        Fetches new messages from API and stores them in database.
        """
        job_name = "periodic_ingestion"
        logger.info(f"Starting {job_name} job...")

        try:
            # Get database session
            async with self.db_manager.session() as session:
                # Create ingestion service
                ingestion_service = IngestionService(
                    session=session,
                    redis_client=self.redis_client,
                    normalize_text=True,
                )

                # Run ingestion
                stats = await ingestion_service.ingest_batch(
                    limit=settings.batch_size,
                    use_cache=True,
                    update_existing=True,
                )

                # Update sync status
                self.sync_status.last_sync = datetime.now()
                if stats.errors == 0:
                    self.sync_status.last_success = datetime.now()
                    self.sync_status.last_error = None
                else:
                    self.sync_status.last_error = f"{stats.errors} errors occurred"

                self.sync_status.last_stats = stats

                logger.info(
                    f"{job_name} completed: "
                    f"{stats.messages_inserted} inserted, "
                    f"{stats.messages_updated} updated in {stats.duration_seconds:.2f}s"
                )

        except Exception as e:
            logger.error(f"{job_name} failed: {e}")
            self.sync_status.last_error = str(e)
            raise JobExecutionError(job_name=job_name, reason=str(e)) from e

    async def _cleanup_job(self) -> None:
        """
        Periodic cleanup job.

        Removes messages older than history_days.
        """
        job_name = "periodic_cleanup"
        logger.info(f"Starting {job_name} job...")

        try:
            # Get database session
            async with self.db_manager.session() as session:
                # Create ingestion service
                ingestion_service = IngestionService(
                    session=session,
                    redis_client=self.redis_client,
                )

                # Run cleanup
                deleted_count = await ingestion_service.cleanup_old_messages(
                    days=settings.history_days
                )

                logger.info(
                    f"{job_name} completed: {deleted_count} old messages deleted"
                )

        except Exception as e:
            logger.error(f"{job_name} failed: {e}")
            raise JobExecutionError(job_name=job_name, reason=str(e)) from e

    async def _health_check_job(self) -> None:
        """
        Periodic health check job.

        Checks health of database, API, and Redis.
        """
        job_name = "health_check"
        logger.debug(f"Running {job_name}...")

        try:
            async with self.db_manager.session() as session:
                ingestion_service = IngestionService(
                    session=session,
                    redis_client=self.redis_client,
                )

                health = await ingestion_service.health_check()

                if not all(v for v in health.values() if v is not None):
                    unhealthy = [k for k, v in health.items() if v is False]
                    logger.warning(f"Health check: unhealthy components: {unhealthy}")
                else:
                    logger.debug("Health check: all components healthy")

        except Exception as e:
            logger.error(f"{job_name} failed: {e}")

    async def _analytics_aggregation_job(self) -> None:
        """
        Periodic analytics aggregation job.

        Aggregates analytics for the last completed 5-minute time slot.
        Runs every 5 minutes to calculate statistics per channel per time slot.
        """
        job_name = "analytics_aggregation"
        logger.info(f"Starting {job_name} job...")

        try:
            # Get database session
            async with self.db_manager.session() as session:
                # Create analytics aggregation service
                aggregation_service = AnalyticsAggregationService(session=session)

                # Aggregate the last completed 5-minute slot
                stats = await aggregation_service.aggregate_last_5_minutes()

                logger.info(
                    f"{job_name} completed: "
                    f"{stats['records_created']} created, "
                    f"{stats['records_updated']} updated, "
                    f"{stats['channels_with_data']}/{stats['channels_processed']} channels had data"
                )

        except Exception as e:
            logger.error(f"{job_name} failed: {e}")
            raise JobExecutionError(job_name=job_name, reason=str(e)) from e

    async def _auto_sync_job(self) -> None:
        """
        Periodic auto sync job.

        Automatically syncs new messages from API every few minutes.
        This ensures continuous data ingestion without manual intervention.
        """
        job_name = "auto_sync"
        logger.info(f"Starting {job_name} job...")

        try:
            # Get database session
            async with self.db_manager.session() as session:
                # Import here to avoid circular dependency
                from src.services.smart_sync_service import SmartSyncService

                # Create sync service
                sync_service = SmartSyncService(
                    session=session,
                    redis_client=self.redis_client,
                )

                # Run auto sync (forward only, background mode)
                result = await sync_service.auto_sync(
                    batch_size=500,  # Process 500 messages at a time
                    forward_only=True,  # Only get new messages
                    background=False,  # Wait for completion in job
                )

                # Log results
                if result.get("status") == "success":
                    forward_result = result.get("forward", {})
                    new_msgs = result.get("total_new_messages", 0)

                    logger.info(
                        f"{job_name} completed: "
                        f"{new_msgs} new messages, "
                        f"{forward_result.get('updated_messages', 0)} updated"
                    )
                else:
                    logger.warning(f"{job_name} returned status: {result.get('status')}")

        except Exception as e:
            logger.error(f"{job_name} failed: {e}")
            # Don't raise exception to prevent job from stopping
            # Just log the error and continue

    def add_ingestion_job(
        self,
        interval_seconds: Optional[int] = None,
        job_id: str = "ingestion_job",
    ) -> None:
        """
        Add periodic ingestion job.

        Args:
            interval_seconds: Interval in seconds (default: from config)
            job_id: Job identifier
        """
        interval = interval_seconds or self.ingestion_interval

        self.scheduler.add_job(
            self._ingestion_job,
            trigger=IntervalTrigger(seconds=interval),
            id=job_id,
            name="Periodic Message Ingestion",
            replace_existing=True,
            max_instances=1,  # Prevent concurrent runs
        )

        logger.info(f"Added ingestion job: every {interval} seconds")

    def add_cleanup_job(
        self,
        hour: Optional[int] = None,
        job_id: str = "cleanup_job",
    ) -> None:
        """
        Add daily cleanup job.

        Args:
            hour: Hour of day to run (0-23, default: from config)
            job_id: Job identifier
        """
        cleanup_hour = hour if hour is not None else self.cleanup_hour

        self.scheduler.add_job(
            self._cleanup_job,
            trigger=CronTrigger(hour=cleanup_hour, minute=0),
            id=job_id,
            name="Daily Cleanup",
            replace_existing=True,
            max_instances=1,
        )

        logger.info(f"Added cleanup job: daily at {cleanup_hour}:00")

    def add_health_check_job(
        self,
        interval_minutes: int = 5,
        job_id: str = "health_check_job",
    ) -> None:
        """
        Add periodic health check job.

        Args:
            interval_minutes: Interval in minutes (default: 5)
            job_id: Job identifier
        """
        self.scheduler.add_job(
            self._health_check_job,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id=job_id,
            name="Health Check",
            replace_existing=True,
            max_instances=1,
        )

        logger.info(f"Added health check job: every {interval_minutes} minutes")

    def add_analytics_aggregation_job(
        self,
        interval_minutes: int = 5,
        job_id: str = "analytics_aggregation_job",
    ) -> None:
        """
        Add periodic analytics aggregation job.

        Args:
            interval_minutes: Interval in minutes (default: 5)
            job_id: Job identifier
        """
        self.scheduler.add_job(
            self._analytics_aggregation_job,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id=job_id,
            name="Analytics Aggregation",
            replace_existing=True,
            max_instances=1,
        )

        logger.info(f"Added analytics aggregation job: every {interval_minutes} minutes")

    def add_auto_sync_job(
        self,
        interval_minutes: int = 3,
        job_id: str = "auto_sync_job",
    ) -> None:
        """
        Add periodic auto sync job.

        Args:
            interval_minutes: Interval in minutes (default: 3)
            job_id: Job identifier
        """
        self.scheduler.add_job(
            self._auto_sync_job,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id=job_id,
            name="Auto Sync",
            replace_existing=True,
            max_instances=1,  # Prevent concurrent runs
        )

        logger.info(f"Added auto sync job: every {interval_minutes} minutes")

    def add_custom_job(
        self,
        func: Callable,
        trigger,
        job_id: str,
        name: str,
        **kwargs
    ) -> None:
        """
        Add a custom job.

        Args:
            func: Job function
            trigger: APScheduler trigger
            job_id: Job identifier
            name: Job name
            **kwargs: Additional scheduler arguments
        """
        self.scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            name=name,
            replace_existing=True,
            **kwargs
        )

        logger.info(f"Added custom job: {name} ({job_id})")

    def start(self) -> None:
        """
        Start the scheduler.

        Adds default jobs and starts scheduler.
        """
        if self._is_running:
            logger.warning("Scheduler is already running")
            return

        try:
            # Add default jobs
            self.add_ingestion_job()
            self.add_cleanup_job()
            self.add_health_check_job()
            self.add_analytics_aggregation_job()
            self.add_auto_sync_job()

            # Start scheduler
            self.scheduler.start()
            self._is_running = True
            self.sync_status.is_running = True

            logger.info("Scheduler started successfully")

            # Calculate next run times
            jobs = self.scheduler.get_jobs()
            for job in jobs:
                next_run = job.next_run_time
                logger.info(f"  - {job.name}: next run at {next_run}")

        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            raise SchedulerError(f"Scheduler start failed: {str(e)}") from e

    def stop(self, wait: bool = True) -> None:
        """
        Stop the scheduler.

        Args:
            wait: Wait for running jobs to complete (default: True)
        """
        if not self._is_running:
            logger.warning("Scheduler is not running")
            return

        try:
            self.scheduler.shutdown(wait=wait)
            self._is_running = False
            self.sync_status.is_running = False

            logger.info("Scheduler stopped")

        except Exception as e:
            logger.error(f"Failed to stop scheduler: {e}")
            raise SchedulerError(f"Scheduler stop failed: {str(e)}") from e

    def pause_job(self, job_id: str) -> None:
        """
        Pause a specific job.

        Args:
            job_id: Job identifier
        """
        try:
            self.scheduler.pause_job(job_id)
            logger.info(f"Job '{job_id}' paused")
        except Exception as e:
            logger.error(f"Failed to pause job '{job_id}': {e}")
            raise SchedulerError(f"Failed to pause job: {str(e)}") from e

    def resume_job(self, job_id: str) -> None:
        """
        Resume a paused job.

        Args:
            job_id: Job identifier
        """
        try:
            self.scheduler.resume_job(job_id)
            logger.info(f"Job '{job_id}' resumed")
        except Exception as e:
            logger.error(f"Failed to resume job '{job_id}': {e}")
            raise SchedulerError(f"Failed to resume job: {str(e)}") from e

    def remove_job(self, job_id: str) -> None:
        """
        Remove a job from scheduler.

        Args:
            job_id: Job identifier
        """
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Job '{job_id}' removed")
        except Exception as e:
            logger.error(f"Failed to remove job '{job_id}': {e}")
            raise SchedulerError(f"Failed to remove job: {str(e)}") from e

    def get_jobs(self) -> list[Dict[str, Any]]:
        """
        Get list of all jobs.

        Returns:
            List of job information dicts
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            })
        return jobs

    def get_status(self) -> SyncStatusSchema:
        """
        Get current sync status.

        Returns:
            Sync status schema
        """
        # Update next_scheduled from ingestion job
        try:
            job = self.scheduler.get_job("ingestion_job")
            if job:
                self.sync_status.next_scheduled = job.next_run_time
        except:
            pass

        return self.sync_status

    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._is_running

    async def run_ingestion_now(self) -> None:
        """
        Manually trigger ingestion job immediately.

        Useful for testing or manual sync.
        """
        logger.info("Manually triggering ingestion job...")
        await self._ingestion_job()

    async def run_cleanup_now(self) -> None:
        """
        Manually trigger cleanup job immediately.

        Useful for testing or manual cleanup.
        """
        logger.info("Manually triggering cleanup job...")
        await self._cleanup_job()
