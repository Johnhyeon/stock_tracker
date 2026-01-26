"""포지션 파싱 서비스 - 빠른 입력 및 텍스트 파싱."""
import re
import logging
from dataclasses import dataclass
from typing import Optional, List, Tuple
from decimal import Decimal, InvalidOperation

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from models import Stock
from utils.korean import is_chosung_only

logger = logging.getLogger(__name__)


@dataclass
class ParsedPosition:
    """파싱된 포지션 데이터."""
    stock_code: Optional[str] = None
    stock_name: Optional[str] = None
    quantity: Optional[int] = None
    avg_price: Optional[Decimal] = None
    current_price: Optional[Decimal] = None
    profit_loss: Optional[Decimal] = None
    profit_loss_rate: Optional[float] = None
    raw_text: str = ""
    is_valid: bool = False
    error: Optional[str] = None


class PositionParser:
    """포지션 파서."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def parse_quick_input(self, text: str) -> ParsedPosition:
        """
        빠른 입력 텍스트 파싱.

        지원 형식:
            - "삼성전자 100 70000" → 삼성전자 100주 @ 70,000원
            - "005930 100 70000" → 삼성전자 100주 @ 70,000원
            - "ㅅㅅㅈㅈ 100 70000" → 삼성전자 100주 @ 70,000원 (초성 검색)
            - "삼성전자 100" → 삼성전자 100주 (가격 없음)
            - "삼성전자" → 삼성전자 (수량, 가격 없음)

        Args:
            text: 입력 텍스트

        Returns:
            ParsedPosition 객체
        """
        result = ParsedPosition(raw_text=text)

        try:
            # 공백 및 쉼표로 분리
            parts = re.split(r'[\s,]+', text.strip())

            if not parts:
                result.error = "입력이 비어있습니다."
                return result

            # 첫 번째 부분: 종목 식별자 (이름, 코드, 또는 초성)
            stock_query = parts[0]
            stock = await self._find_stock(stock_query)

            if not stock:
                result.error = f"종목을 찾을 수 없습니다: {stock_query}"
                return result

            result.stock_code = stock.code
            result.stock_name = stock.name

            # 두 번째 부분: 수량 (선택)
            if len(parts) >= 2:
                try:
                    result.quantity = int(parts[1].replace(',', ''))
                except ValueError:
                    result.error = f"수량 형식 오류: {parts[1]}"
                    return result

            # 세 번째 부분: 평균 매수가 (선택)
            if len(parts) >= 3:
                try:
                    result.avg_price = Decimal(parts[2].replace(',', ''))
                except InvalidOperation:
                    result.error = f"가격 형식 오류: {parts[2]}"
                    return result

            result.is_valid = True

        except Exception as e:
            result.error = f"파싱 오류: {str(e)}"
            logger.exception(f"Position parsing error: {text}")

        return result

    async def parse_bulk_text(self, text: str) -> List[ParsedPosition]:
        """
        여러 줄 텍스트에서 포지션 일괄 파싱.

        각 줄은 빠른 입력 형식을 따릅니다.

        Args:
            text: 여러 줄 텍스트

        Returns:
            ParsedPosition 리스트
        """
        results = []
        lines = text.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):  # 빈 줄 또는 주석 무시
                continue

            parsed = await self.parse_quick_input(line)
            results.append(parsed)

        return results

    async def parse_brokerage_text(self, text: str) -> List[ParsedPosition]:
        """
        증권사 복사 텍스트 파싱.

        일반적인 증권사 포맷:
            종목명 | 수량 | 평균매수가 | 현재가 | 수익률

        Args:
            text: 증권사에서 복사한 텍스트

        Returns:
            ParsedPosition 리스트
        """
        results = []
        lines = text.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 탭 또는 | 로 분리
            if '\t' in line:
                parts = [p.strip() for p in line.split('\t')]
            elif '|' in line:
                parts = [p.strip() for p in line.split('|')]
            else:
                parts = re.split(r'\s{2,}', line)  # 2개 이상 공백으로 분리

            if len(parts) < 2:
                continue

            result = ParsedPosition(raw_text=line)

            try:
                # 첫 번째: 종목명 또는 코드
                stock_query = parts[0]
                # 종목코드와 이름이 같이 있는 경우 분리
                match = re.match(r'(\d{6})\s*(.*)', stock_query)
                if match:
                    stock_query = match.group(1)

                stock = await self._find_stock(stock_query)
                if not stock:
                    result.error = f"종목을 찾을 수 없습니다: {stock_query}"
                    results.append(result)
                    continue

                result.stock_code = stock.code
                result.stock_name = stock.name

                # 숫자 파싱 시도
                numbers = self._extract_numbers(parts[1:])

                if len(numbers) >= 1:
                    result.quantity = int(numbers[0])
                if len(numbers) >= 2:
                    result.avg_price = Decimal(str(numbers[1]))
                if len(numbers) >= 3:
                    result.current_price = Decimal(str(numbers[2]))
                if len(numbers) >= 4:
                    result.profit_loss_rate = numbers[3]

                result.is_valid = True

            except Exception as e:
                result.error = f"파싱 오류: {str(e)}"

            results.append(result)

        return results

    async def _find_stock(self, query: str) -> Optional[Stock]:
        """
        종목 검색.

        Args:
            query: 종목 코드, 이름, 또는 초성

        Returns:
            Stock 객체 또는 None
        """
        query = query.strip()

        # 6자리 숫자면 코드로 검색
        if re.match(r'^\d{6}$', query):
            result = await self.db.execute(
                select(Stock).where(Stock.code == query)
            )
            return result.scalar_one_or_none()

        # 초성 검색
        if is_chosung_only(query):
            result = await self.db.execute(
                select(Stock)
                .where(Stock.name_chosung.startswith(query))
                .limit(1)
            )
            return result.scalar_one_or_none()

        # 이름 검색 (정확히 일치 우선)
        result = await self.db.execute(
            select(Stock).where(Stock.name == query)
        )
        stock = result.scalar_one_or_none()
        if stock:
            return stock

        # 부분 일치 검색
        result = await self.db.execute(
            select(Stock)
            .where(Stock.name.contains(query))
            .order_by(Stock.name)
            .limit(1)
        )
        return result.scalar_one_or_none()

    def _extract_numbers(self, parts: List[str]) -> List[float]:
        """
        문자열 리스트에서 숫자 추출.

        Args:
            parts: 문자열 리스트

        Returns:
            숫자 리스트
        """
        numbers = []
        for part in parts:
            # 쉼표, 원, %, +, - 제거
            cleaned = re.sub(r'[,원%+]', '', part.strip())
            try:
                numbers.append(float(cleaned))
            except ValueError:
                continue
        return numbers
