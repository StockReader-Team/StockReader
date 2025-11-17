"""
Smart sync service for intelligent message synchronization.

این سرویس مشکل از دست رفتن پیام‌های جدید رو حل میکنه با:
1. ابتدا همیشه پیام‌های جدید رو دریافت میکنه (offset=0)
2. سپس به سمت پیام‌های قدیمی میره
3. وضعیت sync رو ذخیره میکنه تا در صورت قطع شدن از همونجا ادامه بده
"""
from datetime import datetime
from typing import Optional, Dict, Any
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.sync_state import SyncState
from src.services.ingestion_service import IngestionService
from src.schemas.ingestion import IngestionStatsSchema
from src.core.logging import get_logger

logger = get_logger(__name__)


class SmartSyncService:
    """
    سرویس هوشمند برای sync پیام‌ها.

    استراتژی:
    1. Forward Sync: همیشه اول پیام‌های جدید (offset=0) رو میگیره
    2. Backward Sync: بعد از اتمام forward، به سمت قدیمی‌ها میره
    3. State Management: وضعیت sync رو ذخیره میکنه
    """

    def __init__(self, session: AsyncSession):
        """Initialize smart sync service."""
        self.session = session
        self.ingestion_service = IngestionService(session)

    async def get_or_create_sync_state(self, direction: str) -> SyncState:
        """Get or create sync state for a direction."""
        result = await self.session.execute(
            select(SyncState)
            .where(SyncState.direction == direction)
            .order_by(SyncState.created_at.desc())
        )
        state = result.scalar_one_or_none()

        if not state:
            state = SyncState(
                direction=direction,
                current_offset=0,
                messages_synced=0,
                is_running=False,
                is_completed=False
            )
            self.session.add(state)
            await self.session.commit()
            await self.session.refresh(state)

        return state

    async def sync_new_messages(
        self,
        batch_size: int = 1000,
        max_batches: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        همیشه پیام‌های جدید رو دریافت میکنه.

        این متد همیشه از offset=0 شروع میکنه تا پیام‌های جدید از دست نرن.

        Args:
            batch_size: تعداد پیام در هر batch
            max_batches: حداکثر تعداد batch (None = بدون محدودیت)

        Returns:
            آمار sync شامل تعداد پیام‌های جدید
        """
        logger.info("🔄 شروع sync پیام‌های جدید...")

        state = await self.get_or_create_sync_state("forward")

        if state.is_running:
            return {
                "status": "already_running",
                "message": "Forward sync در حال اجرا است"
            }

        # Mark as running
        state.is_running = True
        state.last_sync_at = datetime.utcnow()
        await self.session.commit()

        try:
            total_new = 0
            total_updated = 0
            batches_processed = 0

            # همیشه از offset=0 شروع میکنیم (جدیدترین پیام‌ها)
            offset = 0

            while True:
                if max_batches and batches_processed >= max_batches:
                    logger.info(f"✅ رسیدیم به حداکثر batch: {max_batches}")
                    break

                logger.info(
                    f"📥 دریافت batch {batches_processed + 1} "
                    f"(offset={offset}, limit={batch_size})..."
                )

                # Fetch batch
                batch_stats = await self.ingestion_service.ingest_batch(
                    limit=batch_size,
                    offset=offset,
                    use_cache=True,
                    update_existing=True
                )

                total_new += batch_stats.messages_inserted
                total_updated += batch_stats.messages_updated
                batches_processed += 1

                # اگر پیام جدیدی نیومد، یعنی به انتها رسیدیم
                if batch_stats.messages_inserted == 0:
                    logger.info("✅ پیام جدیدی وجود ندارد")
                    break

                # اگر کمتر از batch_size پیام گرفتیم، یعنی تموم شد
                if batch_stats.messages_processed < batch_size:
                    logger.info("✅ به انتهای پیام‌های جدید رسیدیم")
                    break

                offset += batch_size

                # یه استراحت کوتاه بین batchها
                await asyncio.sleep(0.5)

            # Update state
            state.messages_synced += total_new
            state.current_offset = offset
            state.is_running = False
            state.is_completed = (total_new == 0)
            await self.session.commit()

            logger.info(
                f"✅ Forward sync کامل شد: "
                f"{total_new} پیام جدید، {total_updated} به‌روزرسانی"
            )

            return {
                "status": "success",
                "direction": "forward",
                "new_messages": total_new,
                "updated_messages": total_updated,
                "batches_processed": batches_processed,
                "total_synced": state.messages_synced
            }

        except Exception as e:
            logger.error(f"❌ خطا در forward sync: {e}")
            state.is_running = False
            state.last_error = str(e)
            await self.session.commit()
            raise

    async def sync_historical_messages(
        self,
        batch_size: int = 1000,
        max_batches: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        پیام‌های قدیمی رو دریافت میکنه.

        این متد بعد از اتمام forward sync اجرا میشه و از offset قبلی ادامه میده.

        Args:
            batch_size: تعداد پیام در هر batch
            max_batches: حداکثر تعداد batch

        Returns:
            آمار sync
        """
        logger.info("⏪ شروع sync پیام‌های قدیمی...")

        state = await self.get_or_create_sync_state("backward")

        if state.is_running:
            return {
                "status": "already_running",
                "message": "Backward sync در حال اجرا است"
            }

        # Check if forward sync is complete
        forward_state = await self.get_or_create_sync_state("forward")
        if forward_state.is_running:
            return {
                "status": "waiting",
                "message": "منتظر اتمام forward sync هستیم"
            }

        # Mark as running
        state.is_running = True
        state.last_sync_at = datetime.utcnow()
        await self.session.commit()

        try:
            total_new = 0
            total_updated = 0
            batches_processed = 0

            # از offset قبلی ادامه میدیم
            # اگر forward sync کامل شده، از offset آخر forward شروع میکنیم
            if forward_state.is_completed and state.current_offset == 0:
                offset = forward_state.current_offset
            else:
                offset = state.current_offset

            while True:
                if max_batches and batches_processed >= max_batches:
                    logger.info(f"✅ رسیدیم به حداکثر batch: {max_batches}")
                    break

                logger.info(
                    f"📥 دریافت batch {batches_processed + 1} "
                    f"(offset={offset}, limit={batch_size})..."
                )

                # Fetch batch
                batch_stats = await self.ingestion_service.ingest_batch(
                    limit=batch_size,
                    offset=offset,
                    use_cache=True,
                    update_existing=True
                )

                total_new += batch_stats.messages_inserted
                total_updated += batch_stats.messages_updated
                batches_processed += 1

                # اگر کمتر از batch_size پیام گرفتیم، به انتها رسیدیم
                if batch_stats.messages_processed < batch_size:
                    logger.info("✅ به انتهای پیام‌ها رسیدیم")
                    state.is_completed = True
                    break

                offset += batch_size
                state.current_offset = offset
                await self.session.commit()

                await asyncio.sleep(0.5)

            # Update final state
            state.messages_synced += total_new
            state.current_offset = offset
            state.is_running = False
            await self.session.commit()

            logger.info(
                f"✅ Backward sync کامل شد: "
                f"{total_new} پیام جدید، {total_updated} به‌روزرسانی"
            )

            return {
                "status": "success",
                "direction": "backward",
                "new_messages": total_new,
                "updated_messages": total_updated,
                "batches_processed": batches_processed,
                "current_offset": offset,
                "is_completed": state.is_completed
            }

        except Exception as e:
            logger.error(f"❌ خطا در backward sync: {e}")
            state.is_running = False
            state.last_error = str(e)
            await self.session.commit()
            raise

    async def auto_sync(
        self,
        batch_size: int = 1000,
        max_batches_per_direction: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Auto sync: ابتدا forward، سپس backward.

        این بهترین روش sync هست که تضمین میکنه پیام جدید از دست نره.
        """
        logger.info("🚀 شروع Auto Sync...")

        # Step 1: Sync new messages first
        forward_result = await self.sync_new_messages(
            batch_size=batch_size,
            max_batches=max_batches_per_direction
        )

        # Step 2: Sync historical messages
        backward_result = await self.sync_historical_messages(
            batch_size=batch_size,
            max_batches=max_batches_per_direction
        )

        return {
            "status": "success",
            "forward": forward_result,
            "backward": backward_result,
            "total_new_messages": (
                forward_result.get("new_messages", 0) +
                backward_result.get("new_messages", 0)
            )
        }

    async def get_sync_status(self) -> Dict[str, Any]:
        """وضعیت sync رو برمیگردونه."""
        forward_state = await self.get_or_create_sync_state("forward")
        backward_state = await self.get_or_create_sync_state("backward")

        return {
            "forward": {
                "is_running": forward_state.is_running,
                "is_completed": forward_state.is_completed,
                "messages_synced": forward_state.messages_synced,
                "current_offset": forward_state.current_offset,
                "last_sync": forward_state.last_sync_at.isoformat() if forward_state.last_sync_at else None,
                "last_error": forward_state.last_error
            },
            "backward": {
                "is_running": backward_state.is_running,
                "is_completed": backward_state.is_completed,
                "messages_synced": backward_state.messages_synced,
                "current_offset": backward_state.current_offset,
                "last_sync": backward_state.last_sync_at.isoformat() if backward_state.last_sync_at else None,
                "last_error": backward_state.last_error
            }
        }

    async def reset_sync_state(self, direction: Optional[str] = None) -> Dict[str, Any]:
        """Reset sync state."""
        if direction:
            state = await self.get_or_create_sync_state(direction)
            state.current_offset = 0
            state.messages_synced = 0
            state.is_running = False
            state.is_completed = False
            state.last_error = None
            await self.session.commit()
            return {"status": "success", "direction": direction}
        else:
            # Reset both
            for dir in ["forward", "backward"]:
                state = await self.get_or_create_sync_state(dir)
                state.current_offset = 0
                state.messages_synced = 0
                state.is_running = False
                state.is_completed = False
                state.last_error = None
            await self.session.commit()
            return {"status": "success", "direction": "all"}
