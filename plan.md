# YouTube + KIS 주가/거래량 상관관계 분석 기능

## 목표
YouTube 언급량 증가 + 주가/거래량 움직임을 결합하여 "관심 시그널" 순위 제공

## 분석 지표

### 1. YouTube 지표 (기존)
- `mention_count`: 언급 횟수
- `growth_rate`: 언급 증가율 (최근 vs 이전 기간)
- `total_views`: 총 조회수

### 2. KIS 주가 지표 (추가)
- `price_change_rate`: 당일 주가 변동률 (%)
- `volume`: 당일 거래량
- `volume_ratio`: 거래량 증가율 (당일 vs 20일 평균)
- `price_trend`: 5일 주가 추세 (%)

### 3. 복합 시그널 점수 계산
```
signal_score = (
    youtube_score * 0.4 +    # YouTube 버즈 (언급증가율 + 조회수)
    volume_score * 0.35 +    # 거래량 시그널 (거래량 급증)
    price_score * 0.25       # 주가 모멘텀 (변동률)
)
```

**해석:**
- 점수 높음 = YouTube 화제 + 거래량 급증 + 주가 상승 → 강한 매수 시그널
- YouTube만 높고 거래량 낮음 = 아직 시장 반영 안됨 → 선행 기회?
- 거래량만 높고 YouTube 낮음 = 기관/세력 움직임? → 추가 관찰 필요

## 구현 계획

### Phase 1: 백엔드 API

**1-1. 새 스키마 추가** (`schemas/youtube.py`)
```python
class StockSignalResponse(BaseModel):
    """종목 시그널 응답."""
    stock_code: str
    stock_name: Optional[str]

    # YouTube 지표
    mention_count: int
    mention_growth_rate: float  # %
    total_views: int

    # 주가 지표
    current_price: float
    price_change_rate: float  # %
    volume: int
    volume_ratio: float  # 거래량 / 20일 평균

    # 복합 점수
    signal_score: float  # 0-100
    signal_grade: str    # A, B, C, D, F
```

**1-2. 서비스 함수 추가** (`services/youtube_service.py`)
```python
async def get_stock_signals(
    self,
    days_back: int = 7,
    limit: int = 20,
) -> list[dict]:
    """YouTube 언급 + 주가/거래량 결합 시그널 계산."""
    # 1. YouTube 급상승 종목 조회
    # 2. KIS API로 현재가/거래량 조회
    # 3. 20일 평균 거래량 계산 (OHLCV)
    # 4. 복합 점수 계산
    # 5. 순위 정렬 반환
```

**1-3. API 엔드포인트** (`api/v1/youtube.py`)
```python
@router.get("/signals")
async def get_stock_signals(
    days_back: int = 7,
    limit: int = 20,
) -> list[StockSignalResponse]:
```

### Phase 2: 프론트엔드 UI

**2-1. 새 탭 또는 섹션 추가** (`YouTubeTrending.tsx`)
- "🎯 시그널 순위" 탭/카드 추가
- 시그널 점수별 색상 표시 (A=빨강, B=주황, ...)
- 각 지표 tooltip으로 상세 표시

**UI 예시:**
```
| 순위 | 종목명 | 시그널 | YouTube | 주가 | 거래량 |
|------|--------|--------|---------|------|--------|
| 1    | 삼성전자 | A (85) | +150% ↑ | +2.3% | 2.5x |
| 2    | SK하이닉스| B (72) | +80% ↑  | +1.1% | 1.8x |
```

## 대안 검토

### 옵션 A: 간단 버전 (추천)
- 당일 주가/거래량만 사용
- API 호출 최소화 (종목당 1회)
- 빠른 응답 가능

### 옵션 B: 상세 버전
- 20일 OHLCV 히스토리 사용
- 더 정확한 거래량 비율 계산
- API 호출 많음 (종목당 2회)

### 옵션 C: 하이브리드
- 현재가 API로 당일 데이터
- 거래량 평균은 DB에 캐싱 (하루 1회 업데이트)

## 결정 사항

- **표시 위치**: 핫 종목 발굴 탭에 통합 (급상승 종목 카드에 시그널 점수 표시)
- **구현 방식**: 하이브리드 (옵션 C)
  - 당일 현재가/거래량: KIS API 실시간 조회
  - 20일 평균 거래량: DB 테이블에 캐싱 (하루 1회 업데이트)

## 구현 순서

1. DB 모델 추가: `StockVolumeCache` 테이블
2. 스케줄러 작업: 매일 20일 평균 거래량 업데이트
3. 서비스 함수: `get_stock_signals()` 추가
4. API 엔드포인트: `/youtube/signals` 추가
5. 프론트엔드: 급상승 종목 카드에 시그널 점수 표시
