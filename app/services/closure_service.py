"""Service module for creating and managing closure records."""
# pylint: disable=duplicate-code
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models import Closure
from app.services.tracker_service import create_tracker_issue_with_attachments

logger = logging.getLogger(__name__)


async def create_closure_with_tracker(db: AsyncSession, closure_data: dict, files=None) -> Closure:
    """
    Creates a closure and associated Tracker issue.

    Parameters:
    - db: SQLAlchemy async session
    - closure_data: Dictionary with closure data
    - files: Optional list of UploadFile objects

    Returns:
    - Closure: Created closure object with relationships loaded
    """
    # Create closure object
    db_closure = Closure(**closure_data)
    db.add(db_closure)
    await db.flush()  # получаем id без commit

    # Загружаем author через selectinload, чтобы избежать lazy load в async-контексте
    result = await db.execute(
        select(Closure)
        .where(Closure.id == db_closure.id)
        .options(selectinload(Closure.author))
    )
    db_closure = result.scalar_one()

    # Attempt to create a ticket in Yandex Tracker
    try:
        tracker_key = await create_tracker_issue_with_attachments(db_closure, db, files)
        db_closure.issue_id = tracker_key
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Не удалось создать тикет в Tracker для closure %d: %s", db_closure.id, e)
        # tracker_key remains None

    await db.commit()  # единственный commit
    await db.refresh(db_closure)

    # Clean up uploaded files
    if files:
        for file in files:
            try:
                await file.close()
            except Exception:  # pylint: disable=broad-except
                pass

    return db_closure
