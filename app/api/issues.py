"""API routes for managing Tracker issues."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Issue
from app.schemas import IssueRead, IssueUpdate
from app.dependencies import verify_admin_key  # noqa: F401

router = APIRouter()


@router.get("/", response_model=List[IssueRead])
async def read_issues(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """Return a list of all issues."""
    result = await db.execute(
        select(Issue)
        .offset(skip)
        .limit(limit)
        .options(selectinload(Issue.closure))
    )
    issues = result.scalars().all()
    return issues


@router.get("/{issue_key}", response_model=IssueRead)
async def read_issue(issue_key: str, db: AsyncSession = Depends(get_db)):
    """Return a single issue by its tracker key."""
    result = await db.execute(
        select(Issue)
        .where(Issue.tracker_key == issue_key)
        .options(selectinload(Issue.closure))
    )
    db_issue = result.scalar_one_or_none()
    if db_issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    return db_issue


@router.patch(
    "/{issue_key}",
    response_model=IssueRead,
    dependencies=[Depends(verify_admin_key)]
)
async def update_issue(
    issue_key: str,
    issue_update: IssueUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update an existing issue by its tracker key."""
    result = await db.execute(
        select(Issue)
        .where(Issue.tracker_key == issue_key)
        .options(selectinload(Issue.closure))
    )
    db_issue = result.scalar_one_or_none()
    if db_issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")

    update_data = issue_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_issue, key, value)

    await db.commit()
    await db.refresh(db_issue)
    return db_issue
