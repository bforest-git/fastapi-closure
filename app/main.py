"""Main FastAPI application module."""
import asyncio
import sys
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler  # pylint: disable=import-error
from slowapi.util import get_remote_address  # pylint: disable=import-error
from slowapi.errors import RateLimitExceeded  # pylint: disable=import-error
from app.api import closures, authors, issues
from app.database import engine
from app.sync import sync_loop


async def run_migrations():
    """Run Alembic migrations asynchronously via subprocess to avoid event loop conflicts."""
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "alembic", "upgrade", "head",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Alembic upgrade failed:\n{stderr.decode()}")


# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan context manager."""
    # Run Alembic migrations
    await run_migrations()

    # Start background sync task
    task = asyncio.create_task(sync_loop())
    yield
    task.cancel()
    await engine.dispose()

app = FastAPI(
    title="Road closure feedback Yandex",
    description="Backend for processing road closure feedback at Yandex Maps",
    lifespan=lifespan
)

# Add rate limiter to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(closures.router, prefix="/closures", tags=["closures"])
app.include_router(authors.router, prefix="/authors", tags=["authors"])
app.include_router(issues.router, prefix="/issues", tags=["issues"])

@app.get("/")
def read_root():
    """Return welcome message."""
    return {"message": "Welcome to the FastAPI project"}
