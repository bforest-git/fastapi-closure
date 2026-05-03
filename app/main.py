import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()
load_dotenv("telegram-bot/.env")

from fastapi import FastAPI
from app.api import closures
from app.database import engine, Base
from app.sync import sync_loop


# Create tables
Base.metadata.create_all(bind=engine)

# Run database migration
from app.database import migrate_database
migrate_database()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background sync task
    task = asyncio.create_task(sync_loop())
    yield
    task.cancel()

app = FastAPI(
    title="Road closure feedback Yandex",
    description="Backend for processing road closure feedback at Yandex Maps",
    lifespan=lifespan
)

app.include_router(closures.router, prefix="/closures", tags=["closures"])

@app.get("/")
def read_root():
    return {"message": "Welcome to the FastAPI project"}