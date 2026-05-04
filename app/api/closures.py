"""API routes for managing road closure reports."""
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile, File, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from slowapi import Limiter  # pylint: disable=import-error
from slowapi.util import get_remote_address  # pylint: disable=import-error

from app.database import get_db
from app.models import Closure, Author
from app.schemas import ClosureRead, ClosureUpdate
from app.dependencies import verify_admin_key
from app.services.closure_service import create_closure_with_tracker

router = APIRouter()

logger = logging.getLogger(__name__)

# Get limiter instance
limiter = Limiter(key_func=get_remote_address)

# File limits
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_FILES = 10


@router.post("/", response_model=ClosureRead, status_code=201)
@limiter.limit("10/minute")
async def create_closure(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    request: Request,  # pylint: disable=unused-argument
    text: str = Form(...),
    user_id: int = Form(...),
    message_id: int = Form(...),
    sent_at: datetime = Form(...),
    files: Optional[List[UploadFile]] = File(default=None),
    db: AsyncSession = Depends(get_db)
):
    """Create a new closure report and optionally attach files."""
    result = await db.execute(select(Author).where(Author.id == user_id))
    author = result.scalar_one_or_none()

    if not author:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Author not found"
        )

    if author.is_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Author is banned"
        )

    # Validate files
    if files:
        if len(files) > MAX_FILES:
            raise HTTPException(status_code=400, detail=f"Too many files (max {MAX_FILES})")

        for file in files:
            content = await file.read()
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"File {file.filename} too large (max {MAX_FILE_SIZE} bytes)"
                )
            await file.seek(0)

    closure_data = {
        "text": text,
        "message_id": message_id,
        "sent_at": sent_at,
        "author_id": author.id,
    }

    db_closure = await create_closure_with_tracker(db, closure_data, files)

    result = await db.execute(
        select(Closure)
        .where(Closure.id == db_closure.id)
        .options(selectinload(Closure.author))
    )
    closure_with_relationships = result.scalar_one_or_none()

    return closure_with_relationships


@router.get("/", response_model=List[ClosureRead])
async def read_closures(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """Return a list of all closures."""
    result = await db.execute(
        select(Closure)
        .offset(skip)
        .limit(limit)
        .options(selectinload(Closure.author))
    )
    closures = result.scalars().all()
    return closures


@router.get("/{closure_id}", response_model=ClosureRead)
async def read_closure(closure_id: int, db: AsyncSession = Depends(get_db)):
    """Return a single closure by ID."""
    result = await db.execute(
        select(Closure)
        .where(Closure.id == closure_id)
        .options(selectinload(Closure.author))
    )
    db_closure = result.scalar_one_or_none()
    if db_closure is None:
        raise HTTPException(status_code=404, detail="Closure not found")
    return db_closure


@router.delete("/{closure_id}", dependencies=[Depends(verify_admin_key)])
async def delete_closure(closure_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a closure by ID."""
    result = await db.execute(select(Closure).where(Closure.id == closure_id))
    db_closure = result.scalar_one_or_none()
    if db_closure is None:
        raise HTTPException(status_code=404, detail="Closure not found")
    await db.delete(db_closure)
    await db.commit()
    return {"ok": True}


@router.patch(
    "/{closure_id}",
    response_model=ClosureRead,
    dependencies=[Depends(verify_admin_key)]
)
async def update_closure(
    closure_id: int,
    closure_update: ClosureUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update an existing closure by ID."""
    result = await db.execute(select(Closure).where(Closure.id == closure_id))
    db_closure = result.scalar_one_or_none()
    if db_closure is None:
        raise HTTPException(status_code=404, detail="Closure not found")

    update_data = closure_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_closure, key, value)

    await db.commit()
    await db.refresh(db_closure)

    result = await db.execute(
        select(Closure)
        .where(Closure.id == db_closure.id)
        .options(selectinload(Closure.author))
    )
    closure_with_relationships = result.scalar_one_or_none()

    return closure_with_relationships
