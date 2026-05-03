from fastapi import FastAPI
from app.api import closures
from app.database import engine, Base

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Road closure feedback Yandex", description="Backend for processing road closure feedback at Yandex Maps")

app.include_router(closures.router, prefix="/closures", tags=["closures"])

@app.get("/")
def read_root():
    return {"message": "Welcome to the FastAPI project"}