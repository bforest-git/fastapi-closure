import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from httpx import AsyncClient, ASGITransport
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

from app.database import Base, get_db
from app.config import settings

# All tests use asyncio event loop
pytest_plugins = ["anyio"]

# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Admin key for tests
ADMIN_KEY = "test-admin-key"

# Import models to register them in Base.metadata
import app.models  # noqa: F401

from app.api import closures, authors, issues

test_app = FastAPI()
test_app.include_router(closures.router, prefix="/closures", tags=["closures"])
test_app.include_router(authors.router, prefix="/authors", tags=["authors"])
test_app.include_router(issues.router, prefix="/issues", tags=["issues"])

@test_app.get("/")
def read_root():
    return {"message": "Welcome to the FastAPI project"}


@pytest_asyncio.fixture(scope="function")
async def engine():
    """Creates in-memory SQLite engine and tables for each test."""
    _engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(engine):
    """Creates session and overrides get_db in app."""
    TestingSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db():
        async with TestingSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    test_app.dependency_overrides[get_db] = override_get_db
    from app.dependencies import verify_admin_key, api_key_header
    authors_verify = verify_admin_key
    issues_verify = verify_admin_key
    closures_verify = verify_admin_key

    def override_verify_admin_key(api_key: str = Depends(api_key_header)):
        if api_key != ADMIN_KEY:
            raise HTTPException(status_code=403, detail="Forbidden")

    def override_verify_admin_key_issues(api_key: str = Depends(api_key_header)):
        if api_key != ADMIN_KEY:
            raise HTTPException(status_code=403, detail="Forbidden")

    def override_verify_admin_key_closures(api_key: str = Depends(api_key_header)):
        if api_key != ADMIN_KEY:
            raise HTTPException(status_code=403, detail="Forbidden")

    test_app.dependency_overrides[authors_verify] = override_verify_admin_key
    test_app.dependency_overrides[issues_verify] = override_verify_admin_key_issues
    test_app.dependency_overrides[closures_verify] = override_verify_admin_key_closures

    yield TestingSessionLocal
    test_app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    """HTTP client for test requests."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
def admin_headers():
    """Headers with valid X-Admin-Key."""
    return {"X-Admin-Key": ADMIN_KEY}


@pytest_asyncio.fixture(scope="function")
async def mock_tracker(db_session):
    """Mocks create_tracker_issue and attach_files_to_issue."""
    with patch("app.services.tracker_service.create_tracker_issue", new_callable=AsyncMock) as mock_create, \
         patch("app.services.tracker_service.attach_files_to_issue", new_callable=AsyncMock) as mock_attach:
        mock_create.return_value = "TEST-1"
        mock_attach.return_value = None
        yield {"create": mock_create, "attach": mock_attach}


@pytest_asyncio.fixture
async def sample_author(db_session):
    """Creates test author in DB."""
    from app.models import Author
    async with db_session() as session:
        author = Author(messenger="telegram", chat_id=12345, is_banned=False)
        session.add(author)
        await session.flush()  # to get author.id before commit
        await session.commit()
        await session.refresh(author)
        return author


@pytest_asyncio.fixture
async def banned_author(db_session):
    """Creates banned author in DB."""
    from app.models import Author
    async with db_session() as session:
        author = Author(messenger="telegram", chat_id=99999, is_banned=True)
        session.add(author)
        await session.flush()  # to get author.id before commit
        await session.commit()
        await session.refresh(author)
        return author


@pytest_asyncio.fixture
async def third_author(db_session):
    """Creates third test author in DB."""
    from app.models import Author
    async with db_session() as session:
        author = Author(messenger="telegram", chat_id=11111, is_banned=False)
        session.add(author)
        await session.flush()  # to get author.id before commit
        await session.commit()
        await session.refresh(author)
        return author


@pytest_asyncio.fixture
async def sample_closure(db_session, sample_author):
    """Creates test closure in DB."""
    from app.models import Closure
    from datetime import datetime
    async with db_session() as session:
        closure = Closure(
            text="Тестовое перекрытие",
            message_id=1001,
            sent_at=datetime(2026, 1, 1, 12, 0, 0),
            author_id=sample_author.id,
        )
        session.add(closure)
        await session.commit()
        await session.refresh(closure)
        return closure


@pytest_asyncio.fixture
async def sample_issue(db_session):
    """Creates test issue in DB."""
    from app.models import Issue
    async with db_session() as session:
        issue = Issue(
            tracker_key="TEST-1",
            status="open",
            is_answered=False,
        )
        session.add(issue)
        await session.commit()
        await session.refresh(issue)
        return issue
