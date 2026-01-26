"""DART 공시 모델."""
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, String, Text, DateTime, Enum, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID

from core.database import Base


class DisclosureType(str, PyEnum):
    """공시 유형."""
    REGULAR = "regular"  # 정기공시
    FAIR = "fair"  # 공정공시
    MATERIAL = "material"  # 주요사항보고
    EXTERNAL_AUDIT = "external_audit"  # 외부감사관련
    OTHER = "other"  # 기타


class DisclosureImportance(str, PyEnum):
    """공시 중요도."""
    HIGH = "high"  # 중요 (실적, 대규모 계약, M&A 등)
    MEDIUM = "medium"  # 보통
    LOW = "low"  # 낮음


class Disclosure(Base):
    """DART 공시 정보."""
    __tablename__ = "disclosures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # DART 공시 기본 정보
    rcept_no = Column(String(20), unique=True, nullable=False)  # 접수번호
    rcept_dt = Column(String(8), nullable=False)  # 접수일자 (YYYYMMDD)
    corp_code = Column(String(10), nullable=False)  # 고유번호
    corp_name = Column(String(100), nullable=False)  # 회사명
    stock_code = Column(String(10), nullable=True)  # 종목코드

    report_nm = Column(String(500), nullable=False)  # 보고서명
    flr_nm = Column(String(100), nullable=True)  # 공시제출인명

    # 분류 정보
    disclosure_type = Column(
        Enum(DisclosureType),
        default=DisclosureType.OTHER,
        nullable=False
    )
    importance = Column(
        Enum(DisclosureImportance),
        default=DisclosureImportance.MEDIUM,
        nullable=False
    )

    # 추가 정보
    summary = Column(Text, nullable=True)  # 요약 (필터링 후 추출)
    is_read = Column(Boolean, default=False, nullable=False)  # 읽음 여부
    url = Column(String(500), nullable=True)  # DART 상세 페이지 URL

    __table_args__ = (
        Index("ix_disclosures_stock_code", "stock_code"),
        Index("ix_disclosures_rcept_dt", "rcept_dt"),
        Index("ix_disclosures_importance", "importance"),
    )

    def __repr__(self):
        return f"<Disclosure {self.rcept_no} - {self.corp_name}: {self.report_nm[:50]}>"
