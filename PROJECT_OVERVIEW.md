# Stock Tracker - 프로젝트 개요

한국 주식 투자 아이디어 추적 및 분석 시스템.
YouTube 언급량, KIS 주가/거래량, 공시, 텔레그램 리포트, Gemini AI 감정분석을 결합하여 투자 시그널을 제공한다.

---

## 기술 스택

### 백엔드

| 구분 | 기술 |
|------|------|
| 프레임워크 | FastAPI 0.109 + Uvicorn |
| 언어 | Python 3.x |
| DB | PostgreSQL (동기 psycopg2 + 비동기 asyncpg) |
| ORM | SQLAlchemy 2.0 |
| 스케줄러 | APScheduler (Asia/Seoul) |
| HTTP 클라이언트 | httpx |
| 텔레그램 | Telethon (MTProto) |
| AI | Google Gemini API |
| 캐시 | 인메모리 TTL (core/cache.py) |
| 설정 | pydantic-settings + .env |
| 기타 | numpy, cachetools, tenacity, feedparser, pykrx |

### 프론트엔드

| 구분 | 기술 |
|------|------|
| 프레임워크 | React 18 + TypeScript 5.3 |
| 빌드 | Vite 5 |
| 스타일링 | Tailwind CSS 3.4 (class 기반 다크모드) |
| 상태 관리 | Zustand |
| 라우팅 | React Router v6 |
| HTTP | Axios |
| 차트 | TradingView lightweight-charts, Recharts |
| 마크다운 | react-md-editor, react-markdown |
| 유틸 | date-fns, clsx |

### 인프라

| 구분 | 기술 |
|------|------|
| 컨테이너 | Docker Compose (db + backend + frontend) |
| DB | PostgreSQL |
| 배포 | Uvicorn (--reload dev) / Vite dev server |

---

## 외부 API 연동 (8개)

| API | 용도 | Rate Limit |
|-----|------|------------|
| KIS (한국투자증권) | 주가 조회, OHLCV, 투자자 수급 | 10 req/sec |
| DART (금융감독원) | 전자공시, 재무제표 | - |
| YouTube Data API | 채널별 동영상 검색, 종목명 추출 | 일일 쿼터 |
| Naver Search API | 뉴스 검색 | - |
| Telegram MTProto | 채널 모니터링, 리포트 수집 | - |
| Google Gemini | 감정분석, 뉴스 분류 | - |
| RSS | 피드 수집 (feedparser) | - |
| pykrx | 한국거래소 보조 데이터 | - |

모든 클라이언트는 `BaseAPIClient`를 상속하며, 토큰 버킷 rate limiter + tenacity 자동 재시도를 내장.

---

## 핵심 기능

### 1. 투자 아이디어 관리

- 아이디어 CRUD (생성/조회/수정/삭제)
- 포지션 관리 (진입/청산/일괄 처리)
- 매매 기록 및 P&L 분석
- 포트폴리오 스냅샷 (일별 자산 추적)

### 2. 시장 데이터 수집

- 종목 OHLCV (일봉/주봉/월봉)
- ETF OHLCV, 시장 지수 OHLCV
- 투자자 수급 (외인/기관/개인)
- 전자공시 (DART)
- 재무제표 수집 및 분석

### 3. 차트 시그널 스캐너 (9개 시그널)

| 시그널 | 설명 |
|--------|------|
| 눌림목 (pullback) | 급등 후 조정 구간에서 지지 확인 |
| 전고점 돌파 (high_breakout) | 60일 고점 돌파 |
| 저항 돌파 시도 (resistance_test) | 저항선 근접 + 거래량 증가 |
| 지지선 테스트 (support_test) | 쌍바닥 패턴 지지 확인 |
| 넥라인 근접 (mss_proximity) | MSS(Market Structure Shift) 레벨 접근 |
| 관성 구간 (momentum_zone) | 급등 후 변동성 수축 구간 |
| 120일선 전환 (ma120_turn) | 장기 이평선 기울기 양전환 |
| 캔들 수축 (candle_squeeze) | 봉 크기 + 거래량 동반 축소 |
| 캔들 확장 (candle_expansion) | 봉 크기 확장 + 양봉 우위 |

### 4. TOP 필터 (매매 후보 스크리닝)

전체 시그널 스캔 결과에서 엄선된 매매 후보 추출:
- 점수 >= 60
- 60일 위치 < 70%
- 거래량비 > 1.5
- 20일 평균 거래대금 >= 10억원
- 기관 + 외인 5일 순매수 > 0

### 5. 백테스트

- 전 종목 OHLCV 슬라이딩 윈도우 시뮬레이션
- 미래 데이터 완전 차단 (look-ahead bias 방지)
- 9개 시그널 + TOP 모드 지원
- 손절/익절/트레일링스톱/적응형 트레일링
- 계좌룰 (-N% 전량 청산 + 쿨다운)
- 코스피/코스닥 벤치마크 비교
- 시그널별 성과, 월별 성과 분석

### 6. 테마 분석

- 테마 맵 (종목-테마 매핑)
- 테마 셋업 점수 (차트 패턴 기반)
- 테마 펄스 (테마별 모멘텀)
- 신흥 테마 감지
- ETF 순환매 시그널

### 7. 수급 분석

- 수급 랭킹 (외인/기관 순매수 상위)
- 섹터별 수급 흐름
- 종목별 투자자 수급 이력

### 8. 뉴스 & 텔레그램

- 텔레그램 채널 모니터링 (키워드 매칭)
- 텔레그램 아이디어 자동 수집
- 텔레그램 리포트 수집 + Gemini 감정분석
- 종목 뉴스 수집 (Naver) + Gemini 분류
- YouTube 채널 언급량 추적
- 전문가 관심종목 워치리스트

### 9. 대시보드 & 인텔리전스

- 대시보드 v2 (포트폴리오 요약, 시그널 현황, 테마 트렌드)
- 마켓 인텔리전스 (시장 전체 종합 분석)
- 내러티브 브리핑 (AI 생성 시장 요약)
- 카탈리스트 추적 (공시/뉴스 이벤트 → 가격 반응 추적)
- 갭 회복 스캔 (갭다운 후 회복 종목 탐지)

### 10. 스마트 스캐너

- 재무 저평가 스크리너 (ROE, 부채비율, 매출성장률)
- 수렴 뷰 (다중 시그널 동시 충족 종목)
- 스마트 스캐너 (복합 조건 필터링)

---

## 스케줄러 작업 (25+개)

### 장 시간 전용 (09:00-15:30)

- 가격 업데이트 (5분), 갭 회복 스캔 (2분)

### 정기 간격

- 공시 수집 (30분), YouTube (6시간), 전문가 동기화 (30분)
- 알림 체크 (5분), 텔레그램 모니터링 (5분)
- 테마 뉴스 (6시간), 테마 셋업 (6시간)
- 종목 뉴스 (핫 2시간 / 전체 6시간 / 분류 3시간)

### 크론 (장 마감 후)

- 스냅샷 (16:00), 차트패턴 (16:30), OHLCV (16:40)
- ETF (16:45), 지수 (16:50), 카탈리스트 (17:00/17:15)
- 내러티브 브리핑 (17:30), 수급 (18:30), 일일 리포트 (19:00)
- 신규 아이디어 OHLCV (07:00), 재무제표 (수·토 03:00)

---

## DB 모델 (35개)

| 분류 | 모델 |
|------|------|
| 핵심 | InvestmentIdea, Position, Stock, Trade, TrackingSnapshot, EventLog |
| 시장 데이터 | StockOHLCV, EtfOHLCV, MarketIndexOHLCV, StockInvestorFlow |
| 테마/패턴 | ThemeSetup, ThemeChartPattern, RisingChartPattern, CatalystEvent |
| 공시/재무 | Disclosure, FinancialStatement, CompanyProfile, DartCorpCode |
| 뉴스/미디어 | StockNews, ThemeNews, ThemeNewsStats, YouTubeMention, TickerMentionStats |
| 텔레그램 | TelegramChannel, TelegramKeywordMatch, TelegramIdea, TelegramReport, ReportSentimentAnalysis |
| 전문가 | ExpertMention, ExpertStats |
| 알림/워치 | AlertRule, NotificationLog, WatchlistItem |
| 시스템 | JobExecutionLog, NarrativeBriefing |

---

## 아키텍처 특징

- **이중 DB 세션**: 동기 (API 엔드포인트) + 비동기 (스케줄러/이벤트)
- **EventBus**: 데이터 변경 이벤트 발행 → 캐시 무효화 자동 처리
- **서버 캐시**: 인메모리 TTL, EventBus 핸들러와 연동
- **Lazy Loading**: 프론트엔드 전체 페이지 lazy import (코드 스플리팅)
- **다크모드**: 시스템 시간 기반 자동 전환
- **Catch-up**: 서버 재시작 시 놓친 데이터 자동 보정
