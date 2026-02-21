from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from schemas import PositionExit, PositionAddBuy, PositionPartialExit, PositionUpdate, PositionResponse
from services import PositionService

router = APIRouter()


@router.get("/{position_id}", response_model=PositionResponse)
def get_position(position_id: UUID, db: Session = Depends(get_db)):
    service = PositionService(db)
    position = service.get(position_id)
    if not position:
        raise HTTPException(status_code=404, detail="포지션을 찾을 수 없습니다.")
    return position


@router.put("/{position_id}", response_model=PositionResponse)
def update_position(position_id: UUID, data: PositionUpdate, db: Session = Depends(get_db)):
    """포지션 수정 (잘못 입력한 매매내역 수정)"""
    service = PositionService(db)
    position = service.update(position_id, data)
    if not position:
        raise HTTPException(status_code=404, detail="포지션을 찾을 수 없습니다.")
    return position


@router.put("/{position_id}/exit", response_model=PositionResponse)
def exit_position(position_id: UUID, data: PositionExit, db: Session = Depends(get_db)):
    service = PositionService(db)
    position = service.exit(position_id, data)
    if not position:
        raise HTTPException(status_code=404, detail="포지션을 찾을 수 없습니다.")
    return position


@router.post("/{position_id}/add-buy", response_model=PositionResponse)
def add_buy_position(position_id: UUID, data: PositionAddBuy, db: Session = Depends(get_db)):
    """추가매수: 평균단가 재계산"""
    service = PositionService(db)
    position = service.add_buy(position_id, data)
    if not position:
        raise HTTPException(status_code=404, detail="포지션을 찾을 수 없거나 이미 청산된 포지션입니다.")
    return position


@router.post("/{position_id}/partial-exit", response_model=PositionResponse)
def partial_exit_position(position_id: UUID, data: PositionPartialExit, db: Session = Depends(get_db)):
    """부분매도: 일부 수량만 매도"""
    service = PositionService(db)
    position = service.partial_exit(position_id, data)
    if not position:
        raise HTTPException(status_code=400, detail="포지션을 찾을 수 없거나 매도 수량이 보유 수량을 초과합니다.")
    return position


@router.delete("/{position_id}", status_code=204)
def delete_position(position_id: UUID, db: Session = Depends(get_db)):
    service = PositionService(db)
    if not service.delete(position_id):
        raise HTTPException(status_code=404, detail="포지션을 찾을 수 없습니다.")
