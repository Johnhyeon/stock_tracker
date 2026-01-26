"""포지션 일괄 입력 관련 스키마."""
from datetime import date
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field


class QuickPositionInput(BaseModel):
    """빠른 입력 요청."""
    text: str = Field(..., description="빠른 입력 텍스트 (예: '삼성전자 100 70000')")


class BulkTextInput(BaseModel):
    """여러 줄 텍스트 입력."""
    text: str = Field(..., description="여러 줄 텍스트 (각 줄이 하나의 포지션)")


class BrokerageTextInput(BaseModel):
    """증권사 복사 텍스트 입력."""
    text: str = Field(..., description="증권사에서 복사한 텍스트")


class ParsedPositionResponse(BaseModel):
    """파싱된 포지션 응답."""
    stock_code: Optional[str] = None
    stock_name: Optional[str] = None
    quantity: Optional[int] = None
    avg_price: Optional[float] = None
    current_price: Optional[float] = None
    profit_loss: Optional[float] = None
    profit_loss_rate: Optional[float] = None
    raw_text: str = ""
    is_valid: bool = False
    error: Optional[str] = None


class ParseResult(BaseModel):
    """파싱 결과."""
    total: int
    valid: int
    invalid: int
    positions: List[ParsedPositionResponse]


class BulkPositionCreate(BaseModel):
    """일괄 포지션 생성 요청."""
    idea_id: Optional[str] = None  # 연결할 아이디어 ID (없으면 새로 생성)
    positions: List[dict] = Field(..., description="생성할 포지션 목록")
    create_ideas: bool = Field(default=True, description="아이디어도 함께 생성할지 여부")


class BulkPositionResult(BaseModel):
    """일괄 생성 결과."""
    total: int
    created: int
    failed: int
    errors: List[str]
    created_position_ids: List[str]


class FileImportResult(BaseModel):
    """파일 임포트 결과."""
    total: int
    success: int
    failed: int
    positions: List[ParsedPositionResponse]
    errors: List[str]
