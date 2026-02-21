"""DART 재무제표 원시 데이터 모델."""
from datetime import datetime

from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Index, UniqueConstraint
from core.database import Base


class FinancialStatement(Base):
    """DART 재무제표 데이터 (계정 단위 저장)."""

    __tablename__ = "financial_statements"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 식별
    stock_code = Column(String(6), nullable=False, index=True, comment="종목코드")
    corp_code = Column(String(8), nullable=False, comment="DART 고유번호")
    bsns_year = Column(String(4), nullable=False, comment="사업연도 (YYYY)")
    reprt_code = Column(String(5), nullable=False, comment="보고서코드 (11011=연간, 11012=반기, 11013=1분기, 11014=3분기)")
    fs_div = Column(String(3), nullable=False, comment="개별/연결 (CFS=연결, OFS=개별)")

    # 분류
    sj_div = Column(String(10), nullable=False, comment="재무제표구분 (BS/IS/CF/SCE/CIS)")
    sj_nm = Column(String(100), nullable=True, comment="재무제표명")
    account_id = Column(String(300), nullable=False, comment="계정ID")
    account_nm = Column(String(200), nullable=False, comment="계정명")
    account_detail = Column(String(500), nullable=True, comment="계정상세")

    # 금액
    thstrm_amount = Column(BigInteger, nullable=True, comment="당기금액")
    frmtrm_amount = Column(BigInteger, nullable=True, comment="전기금액")
    bfefrmtrm_amount = Column(BigInteger, nullable=True, comment="전전기금액")

    # 기간명
    thstrm_nm = Column(String(50), nullable=True, comment="당기명")
    frmtrm_nm = Column(String(50), nullable=True, comment="전기명")
    bfefrmtrm_nm = Column(String(50), nullable=True, comment="전전기명")

    # 메타
    ord = Column(Integer, nullable=True, comment="정렬순서")
    currency = Column(String(3), nullable=True, default="KRW", comment="통화")
    collected_at = Column(DateTime, default=datetime.utcnow, comment="수집일시")

    __table_args__ = (
        Index(
            "ix_fs_lookup",
            "stock_code", "bsns_year", "reprt_code", "fs_div",
        ),
        UniqueConstraint(
            "stock_code", "bsns_year", "reprt_code", "fs_div", "sj_div", "account_id",
            name="uq_fs_account",
        ),
    )

    def __repr__(self):
        return (
            f"<FinancialStatement {self.stock_code} {self.bsns_year} "
            f"{self.reprt_code} {self.fs_div} {self.account_nm}>"
        )
