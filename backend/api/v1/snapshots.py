"""트래킹 스냅샷 API."""
from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from schemas import SnapshotCreate, SnapshotResponse
from services.snapshot_service import SnapshotService

router = APIRouter()


@router.get("/ideas/{idea_id}/snapshots", response_model=List[SnapshotResponse])
def list_snapshots(idea_id: UUID, limit: int = 30, db: Session = Depends(get_db)):
    service = SnapshotService(db)
    return service.get_by_idea(idea_id, limit=limit)


@router.post("/ideas/{idea_id}/snapshots", response_model=SnapshotResponse, status_code=201)
def create_snapshot(idea_id: UUID, data: SnapshotCreate, db: Session = Depends(get_db)):
    service = SnapshotService(db)
    snapshot = service.create(idea_id, data)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Idea not found")
    return snapshot


@router.get("/snapshots/{snapshot_id}", response_model=SnapshotResponse)
def get_snapshot(snapshot_id: UUID, db: Session = Depends(get_db)):
    service = SnapshotService(db)
    snapshot = service.get(snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snapshot


@router.delete("/snapshots/{snapshot_id}", status_code=204)
def delete_snapshot(snapshot_id: UUID, db: Session = Depends(get_db)):
    service = SnapshotService(db)
    if not service.delete(snapshot_id):
        raise HTTPException(status_code=404, detail="Snapshot not found")


@router.get("/portfolio/summary")
def get_portfolio_summary(db: Session = Depends(get_db)):
    """포트폴리오 스냅샷 요약 조회."""
    service = SnapshotService(db)
    return service.get_portfolio_summary()
