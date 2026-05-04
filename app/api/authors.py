"""API routes for managing authors."""
# pylint: disable=duplicate-code
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Author
from app.schemas import AuthorRead, AuthorBanRequest, AuthorCreate
from app.dependencies import verify_admin_key, api_key_header  # noqa: F401

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/ban", response_model=AuthorRead, dependencies=[Depends(verify_admin_key)])
async def ban_author(data: AuthorBanRequest, db: AsyncSession = Depends(get_db)):
    """Ban an author by user ID."""
    result = await db.execute(select(Author).where(Author.id == data.user_id))
    author = result.scalar_one_or_none()

    if not author:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Author not found"
        )

    author.is_banned = True

    await db.commit()
    await db.refresh(author)
    return author


@router.post("/unban", response_model=AuthorRead, dependencies=[Depends(verify_admin_key)])
async def unban_author(data: AuthorBanRequest, db: AsyncSession = Depends(get_db)):
    """Unban an author by user ID."""
    logger.info("unban_author called: user_id=%s", data.user_id)
    result = await db.execute(select(Author).where(Author.id == data.user_id))
    author = result.scalar_one_or_none()

    if not author:
        logger.warning("unban_author: author not found for user_id=%s", data.user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Author not found"
        )

    logger.info("unban_author: found author id=%s is_banned=%s, setting to False", author.id, author.is_banned)
    author.is_banned = False
    await db.commit()
    await db.refresh(author)
    logger.info("unban_author: after commit author id=%s is_banned=%s", author.id, author.is_banned)
    return author


@router.get("/", response_model=list[AuthorRead])
async def list_authors(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """Return a list of all authors."""
    result = await db.execute(select(Author).offset(skip).limit(limit))
    return result.scalars().all()


@router.get("/banned", response_model=list[AuthorRead])
async def list_banned_authors(db: AsyncSession = Depends(get_db)):
    """Return a list of all banned authors."""
    result = await db.execute(select(Author).where(Author.is_banned.is_(True)))
    return result.scalars().all()


@router.get("/search", response_model=AuthorRead)
async def search_author(messenger: str, chat_id: int, db: AsyncSession = Depends(get_db)):
    """Search for an author by messenger and chat ID."""
    result = await db.execute(select(Author).where(
        Author.messenger == messenger,
        Author.chat_id == chat_id
    ))
    author = result.scalar_one_or_none()

    if not author:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Author not found"
        )

    return author


@router.post("/", response_model=AuthorRead, status_code=201)
async def create_author(data: AuthorCreate, db: AsyncSession = Depends(get_db)):
    """Create a new author."""
    result = await db.execute(select(Author).where(
        Author.messenger == data.messenger,
        Author.chat_id == data.chat_id
    ))
    existing_author = result.scalar_one_or_none()

    if existing_author:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Author with this messenger and chat_id already exists"
        )

    author = Author(
        messenger=data.messenger,
        chat_id=data.chat_id,
        is_banned=False
    )
    db.add(author)
    await db.commit()
    await db.refresh(author)
    return author
