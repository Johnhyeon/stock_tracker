"""포지션 일괄 입력 API."""
from uuid import UUID
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from core.timezone import today_kst
from models import InvestmentIdea, Position, IdeaType, IdeaStatus
from schemas.position_bulk import (
    QuickPositionInput,
    BulkTextInput,
    BrokerageTextInput,
    ParsedPositionResponse,
    ParseResult,
    BulkPositionCreate,
    BulkPositionResult,
    FileImportResult,
)
from services.position_parser import PositionParser
from services.file_importer import FileImporter

router = APIRouter(prefix="/positions/bulk", tags=["positions-bulk"])


def _to_response(parsed) -> ParsedPositionResponse:
    """ParsedPosition을 응답 스키마로 변환."""
    return ParsedPositionResponse(
        stock_code=parsed.stock_code,
        stock_name=parsed.stock_name,
        quantity=parsed.quantity,
        avg_price=float(parsed.avg_price) if parsed.avg_price else None,
        current_price=float(parsed.current_price) if parsed.current_price else None,
        profit_loss=float(parsed.profit_loss) if parsed.profit_loss else None,
        profit_loss_rate=parsed.profit_loss_rate,
        raw_text=parsed.raw_text,
        is_valid=parsed.is_valid,
        error=parsed.error,
    )


# ============ 파싱 API ============

@router.post("/parse/quick", response_model=ParsedPositionResponse)
async def parse_quick_input(
    data: QuickPositionInput,
    db: AsyncSession = Depends(get_async_db),
):
    """
    빠른 입력 텍스트 파싱.

    형식: "종목 수량 가격"
    예시: "삼성전자 100 70000" 또는 "ㅅㅅㅈㅈ 100 70000"
    """
    parser = PositionParser(db)
    parsed = await parser.parse_quick_input(data.text)
    return _to_response(parsed)


@router.post("/parse/bulk", response_model=ParseResult)
async def parse_bulk_text(
    data: BulkTextInput,
    db: AsyncSession = Depends(get_async_db),
):
    """
    여러 줄 텍스트 파싱.

    각 줄은 빠른 입력 형식을 따릅니다.
    """
    parser = PositionParser(db)
    results = await parser.parse_bulk_text(data.text)

    valid_count = sum(1 for r in results if r.is_valid)

    return ParseResult(
        total=len(results),
        valid=valid_count,
        invalid=len(results) - valid_count,
        positions=[_to_response(r) for r in results],
    )


@router.post("/parse/brokerage", response_model=ParseResult)
async def parse_brokerage_text(
    data: BrokerageTextInput,
    db: AsyncSession = Depends(get_async_db),
):
    """
    증권사 복사 텍스트 파싱.

    탭 또는 | 로 구분된 형식 지원.
    """
    parser = PositionParser(db)
    results = await parser.parse_brokerage_text(data.text)

    valid_count = sum(1 for r in results if r.is_valid)

    return ParseResult(
        total=len(results),
        valid=valid_count,
        invalid=len(results) - valid_count,
        positions=[_to_response(r) for r in results],
    )


# ============ 파일 임포트 API ============

@router.post("/import/csv", response_model=FileImportResult)
async def import_csv_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db),
):
    """
    CSV 파일 임포트.

    지원 컬럼: 종목코드, 종목명, 수량, 평균매수가 등
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="CSV 파일만 지원됩니다.")

    content = await file.read()
    importer = FileImporter(db)
    result = await importer.import_csv(content)

    return FileImportResult(
        total=result.total,
        success=result.success,
        failed=result.failed,
        positions=[_to_response(p) for p in result.positions],
        errors=result.errors,
    )


@router.post("/import/json", response_model=FileImportResult)
async def import_json_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db),
):
    """
    JSON 파일 임포트.

    형식: [{"stock_code": "005930", "quantity": 100, ...}, ...]
    """
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="JSON 파일만 지원됩니다.")

    content = await file.read()
    importer = FileImporter(db)
    result = await importer.import_json(content)

    return FileImportResult(
        total=result.total,
        success=result.success,
        failed=result.failed,
        positions=[_to_response(p) for p in result.positions],
        errors=result.errors,
    )


@router.post("/import/excel", response_model=FileImportResult)
async def import_excel_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Excel 파일 임포트.

    .xlsx 파일만 지원됩니다.
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Excel 파일만 지원됩니다.")

    content = await file.read()
    importer = FileImporter(db)
    result = await importer.import_excel(content)

    return FileImportResult(
        total=result.total,
        success=result.success,
        failed=result.failed,
        positions=[_to_response(p) for p in result.positions],
        errors=result.errors,
    )


# ============ 일괄 생성 API ============

@router.post("/create", response_model=BulkPositionResult)
async def create_bulk_positions(
    data: BulkPositionCreate,
    db: AsyncSession = Depends(get_async_db),
):
    """
    파싱된 포지션 일괄 생성.

    아이디어가 없으면 자동으로 생성합니다.
    """
    result = BulkPositionResult(
        total=len(data.positions),
        created=0,
        failed=0,
        errors=[],
        created_position_ids=[],
    )

    for i, pos_data in enumerate(data.positions):
        try:
            stock_code = pos_data.get('stock_code')
            stock_name = pos_data.get('stock_name', stock_code)
            quantity = pos_data.get('quantity', 1)
            avg_price = pos_data.get('avg_price')

            if not stock_code:
                result.failed += 1
                result.errors.append(f"항목 {i + 1}: 종목 코드가 없습니다.")
                continue

            # 아이디어 찾기 또는 생성
            idea_id = data.idea_id

            if not idea_id and data.create_ideas:
                # 기존 아이디어 검색
                from sqlalchemy import select
                existing = await db.execute(
                    select(InvestmentIdea).where(
                        InvestmentIdea.stock_code == stock_code,
                        InvestmentIdea.status.in_([IdeaStatus.ACTIVE, IdeaStatus.WATCHING])
                    )
                )
                existing_idea = existing.scalar_one_or_none()

                if existing_idea:
                    idea_id = str(existing_idea.id)
                else:
                    # 새 아이디어 생성
                    new_idea = InvestmentIdea(
                        stock_code=stock_code,
                        stock_name=stock_name,
                        idea_type=IdeaType.LONG,
                        thesis=f"빠른 입력으로 생성됨",
                        status=IdeaStatus.ACTIVE,
                        entry_price=Decimal(str(avg_price)) if avg_price else None,
                    )
                    db.add(new_idea)
                    await db.flush()
                    idea_id = str(new_idea.id)

            if not idea_id:
                result.failed += 1
                result.errors.append(f"항목 {i + 1}: 연결할 아이디어가 없습니다.")
                continue

            # 포지션 생성
            position = Position(
                idea_id=UUID(idea_id),
                ticker=stock_code,
                quantity=quantity,
                entry_price=Decimal(str(avg_price)) if avg_price else Decimal('0'),
                entry_date=today_kst(),
            )
            db.add(position)
            await db.flush()

            result.created += 1
            result.created_position_ids.append(str(position.id))

        except Exception as e:
            result.failed += 1
            result.errors.append(f"항목 {i + 1}: {str(e)}")

    await db.commit()
    return result
