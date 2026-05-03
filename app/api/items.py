from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def read_items():
    return [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]

@router.get("/{item_id}")
def read_item(item_id: int):
    return {"id": item_id, "name": f"Item {item_id}"}