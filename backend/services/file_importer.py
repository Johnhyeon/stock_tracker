"""파일 임포트 서비스 - CSV, Excel, JSON 파일 처리."""
import io
import csv
import json
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from decimal import Decimal, InvalidOperation

from sqlalchemy.ext.asyncio import AsyncSession

from services.position_parser import PositionParser, ParsedPosition

logger = logging.getLogger(__name__)


@dataclass
class ImportResult:
    """임포트 결과."""
    total: int = 0
    success: int = 0
    failed: int = 0
    positions: List[ParsedPosition] = None
    errors: List[str] = None

    def __post_init__(self):
        if self.positions is None:
            self.positions = []
        if self.errors is None:
            self.errors = []


class FileImporter:
    """파일 임포터."""

    # 지원되는 컬럼 이름 매핑
    COLUMN_MAPPINGS = {
        'stock_code': ['종목코드', '코드', 'code', 'stock_code', 'ticker', '종목번호'],
        'stock_name': ['종목명', '종목', 'name', 'stock_name', '이름'],
        'quantity': ['수량', '보유수량', 'quantity', 'qty', 'shares', '주수'],
        'avg_price': ['평균매수가', '매수가', '평균가', 'avg_price', 'average_price', 'buy_price', '매입가'],
        'current_price': ['현재가', '시가', 'current_price', 'price', '시세'],
        'profit_loss': ['평가손익', '손익', 'profit_loss', 'pnl', '수익'],
        'profit_loss_rate': ['수익률', '손익률', 'profit_loss_rate', 'return', '%'],
    }

    def __init__(self, db: AsyncSession):
        self.db = db
        self.parser = PositionParser(db)

    async def import_csv(self, content: bytes, encoding: str = 'utf-8') -> ImportResult:
        """
        CSV 파일 임포트.

        Args:
            content: CSV 파일 내용 (바이트)
            encoding: 인코딩 (기본: utf-8)

        Returns:
            ImportResult 객체
        """
        result = ImportResult()

        try:
            text = content.decode(encoding)
        except UnicodeDecodeError:
            # EUC-KR 시도
            try:
                text = content.decode('euc-kr')
            except UnicodeDecodeError:
                result.errors.append("파일 인코딩을 인식할 수 없습니다. UTF-8 또는 EUC-KR로 저장해주세요.")
                return result

        try:
            reader = csv.DictReader(io.StringIO(text))
            rows = list(reader)
            result.total = len(rows)

            # 컬럼 매핑 찾기
            column_map = self._find_column_mapping(reader.fieldnames or [])

            for i, row in enumerate(rows):
                try:
                    parsed = await self._parse_row(row, column_map, i + 1)
                    result.positions.append(parsed)

                    if parsed.is_valid:
                        result.success += 1
                    else:
                        result.failed += 1
                        if parsed.error:
                            result.errors.append(f"행 {i + 1}: {parsed.error}")

                except Exception as e:
                    result.failed += 1
                    result.errors.append(f"행 {i + 1}: {str(e)}")

        except Exception as e:
            result.errors.append(f"CSV 파싱 오류: {str(e)}")
            logger.exception("CSV import error")

        return result

    async def import_json(self, content: bytes) -> ImportResult:
        """
        JSON 파일 임포트.

        지원 형식:
            - 배열: [{"stock_code": "005930", "quantity": 100, ...}, ...]
            - 객체: {"positions": [...]}

        Args:
            content: JSON 파일 내용 (바이트)

        Returns:
            ImportResult 객체
        """
        result = ImportResult()

        try:
            data = json.loads(content.decode('utf-8'))

            # 배열 또는 positions 키 확인
            if isinstance(data, list):
                rows = data
            elif isinstance(data, dict) and 'positions' in data:
                rows = data['positions']
            else:
                result.errors.append("JSON 형식이 올바르지 않습니다. 배열 또는 {positions: [...]} 형식이어야 합니다.")
                return result

            result.total = len(rows)

            for i, row in enumerate(rows):
                try:
                    # JSON은 키 이름이 그대로 사용되므로 직접 매핑
                    parsed = ParsedPosition(raw_text=json.dumps(row, ensure_ascii=False))

                    # 종목 찾기
                    stock_query = row.get('stock_code') or row.get('stock_name') or row.get('code') or row.get('name')
                    if stock_query:
                        stock = await self.parser._find_stock(str(stock_query))
                        if stock:
                            parsed.stock_code = stock.code
                            parsed.stock_name = stock.name
                        else:
                            parsed.error = f"종목을 찾을 수 없습니다: {stock_query}"
                            result.positions.append(parsed)
                            result.failed += 1
                            continue

                    # 수량
                    qty = row.get('quantity') or row.get('qty') or row.get('수량')
                    if qty is not None:
                        parsed.quantity = int(qty)

                    # 평균 매수가
                    price = row.get('avg_price') or row.get('average_price') or row.get('평균매수가')
                    if price is not None:
                        parsed.avg_price = Decimal(str(price))

                    parsed.is_valid = bool(parsed.stock_code)
                    result.positions.append(parsed)

                    if parsed.is_valid:
                        result.success += 1
                    else:
                        result.failed += 1

                except Exception as e:
                    result.failed += 1
                    result.errors.append(f"항목 {i + 1}: {str(e)}")

        except json.JSONDecodeError as e:
            result.errors.append(f"JSON 파싱 오류: {str(e)}")

        return result

    async def import_excel(self, content: bytes) -> ImportResult:
        """
        Excel 파일 임포트.

        Args:
            content: Excel 파일 내용 (바이트)

        Returns:
            ImportResult 객체
        """
        result = ImportResult()

        try:
            import openpyxl
            from io import BytesIO

            workbook = openpyxl.load_workbook(BytesIO(content), data_only=True)
            sheet = workbook.active

            # 첫 번째 행을 헤더로 사용
            headers = [str(cell.value).strip() if cell.value else '' for cell in sheet[1]]
            column_map = self._find_column_mapping(headers)

            rows = list(sheet.iter_rows(min_row=2, values_only=True))
            result.total = len(rows)

            for i, row in enumerate(rows):
                try:
                    row_dict = {headers[j]: row[j] for j in range(min(len(headers), len(row)))}
                    parsed = await self._parse_row(row_dict, column_map, i + 2)
                    result.positions.append(parsed)

                    if parsed.is_valid:
                        result.success += 1
                    else:
                        result.failed += 1
                        if parsed.error:
                            result.errors.append(f"행 {i + 2}: {parsed.error}")

                except Exception as e:
                    result.failed += 1
                    result.errors.append(f"행 {i + 2}: {str(e)}")

        except ImportError:
            result.errors.append("Excel 파일 처리를 위해 openpyxl 패키지가 필요합니다.")
        except Exception as e:
            result.errors.append(f"Excel 파싱 오류: {str(e)}")
            logger.exception("Excel import error")

        return result

    def _find_column_mapping(self, headers: List[str]) -> Dict[str, str]:
        """
        헤더에서 컬럼 매핑 찾기.

        Args:
            headers: 헤더 리스트

        Returns:
            {내부키: 실제헤더명} 딕셔너리
        """
        column_map = {}
        headers_lower = [h.lower().strip() for h in headers]

        for internal_key, aliases in self.COLUMN_MAPPINGS.items():
            for alias in aliases:
                alias_lower = alias.lower()
                if alias_lower in headers_lower:
                    idx = headers_lower.index(alias_lower)
                    column_map[internal_key] = headers[idx]
                    break

        return column_map

    async def _parse_row(
        self,
        row: Dict[str, Any],
        column_map: Dict[str, str],
        row_num: int,
    ) -> ParsedPosition:
        """
        행 데이터 파싱.

        Args:
            row: 행 데이터 딕셔너리
            column_map: 컬럼 매핑
            row_num: 행 번호 (에러 메시지용)

        Returns:
            ParsedPosition 객체
        """
        parsed = ParsedPosition(raw_text=str(row))

        # 종목 찾기 (코드 우선, 없으면 이름으로)
        stock_query = None
        if 'stock_code' in column_map:
            stock_query = row.get(column_map['stock_code'])
        if not stock_query and 'stock_name' in column_map:
            stock_query = row.get(column_map['stock_name'])

        if not stock_query:
            parsed.error = "종목 코드 또는 이름이 없습니다."
            return parsed

        stock_query = str(stock_query).strip()
        stock = await self.parser._find_stock(stock_query)

        if not stock:
            parsed.error = f"종목을 찾을 수 없습니다: {stock_query}"
            return parsed

        parsed.stock_code = stock.code
        parsed.stock_name = stock.name

        # 수량
        if 'quantity' in column_map:
            qty_val = row.get(column_map['quantity'])
            if qty_val is not None:
                try:
                    parsed.quantity = int(float(str(qty_val).replace(',', '')))
                except (ValueError, TypeError):
                    pass

        # 평균 매수가
        if 'avg_price' in column_map:
            price_val = row.get(column_map['avg_price'])
            if price_val is not None:
                try:
                    parsed.avg_price = Decimal(str(price_val).replace(',', ''))
                except (InvalidOperation, TypeError):
                    pass

        # 현재가
        if 'current_price' in column_map:
            price_val = row.get(column_map['current_price'])
            if price_val is not None:
                try:
                    parsed.current_price = Decimal(str(price_val).replace(',', ''))
                except (InvalidOperation, TypeError):
                    pass

        parsed.is_valid = True
        return parsed
