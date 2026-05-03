import logging
import traceback
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Closure
from app.schemas import ClosureCreate, ClosureRead, ClosureStatusUpdate

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/", response_model=ClosureRead, status_code=201)
def create_closure(closure: ClosureCreate, db: Session = Depends(get_db)):
    db_closure = Closure(**closure.model_dump())
    db.add(db_closure)
    db.commit()
    db.refresh(db_closure)
    
    # Попытка создания тикета в Яндекс Трекере
    try:
        from app.tracker import create_tracker_issue
        tracker_key = create_tracker_issue(db_closure)
        db_closure.tracker_key = tracker_key
        db.commit()
        db.refresh(db_closure)
    except Exception as e:
        logger.error(f"Failed to create tracker issue for closure {db_closure.id}: {e}\n{traceback.format_exc()}")
        # tracker_key остается None
    
    return db_closure

@router.get("/", response_model=List[ClosureRead])
def read_closures(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    closures = db.query(Closure).offset(skip).limit(limit).all()
    return closures

@router.get("/{closure_id}", response_model=ClosureRead)
def read_closure(closure_id: int, db: Session = Depends(get_db)):
    db_closure = db.query(Closure).filter(Closure.id == closure_id).first()
    if db_closure is None:
        raise HTTPException(status_code=404, detail="Closure not found")
    return db_closure

@router.delete("/{closure_id}")
def delete_closure(closure_id: int, db: Session = Depends(get_db)):
    db_closure = db.query(Closure).filter(Closure.id == closure_id).first()
    if db_closure is None:
        raise HTTPException(status_code=404, detail="Closure not found")
    db.delete(db_closure)
    db.commit()
    return {"ok": True}

@router.patch("/{closure_id}/status", response_model=ClosureRead)
def update_closure_status(closure_id: int, status_update: ClosureStatusUpdate, db: Session = Depends(get_db)):
    db_closure = db.query(Closure).filter(Closure.id == closure_id).first()
    if db_closure is None:
        raise HTTPException(status_code=404, detail="Closure not found")
    
    db_closure.status = status_update.status
    db.commit()
    db.refresh(db_closure)
    return db_closure