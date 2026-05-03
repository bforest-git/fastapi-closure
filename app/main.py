from fastapi import FastAPI
from app.api import items

app = FastAPI(title="Road closure feedback Yandex", description="Backend for processing road closure feedback at Yandex Maps")

app.include_router(items.router, prefix="/items", tags=["items"])

@app.get("/")
def read_root():
    return {"message": "Welcome to the FastAPI project"}