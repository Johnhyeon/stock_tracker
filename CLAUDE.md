# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

한국 주식 투자 아이디어 추적 및 분석 시스템. YouTube 언급량, KIS 주가/거래량, 공시, 텔레그램 리포트, Gemini AI 감정분석을 결합하여 투자 시그널을 제공합니다.

**GitHub**: https://github.com/Johnhyeon/stock_tracker

## 개발 명령어

### 백엔드 (FastAPI + PostgreSQL)

**중요**: 반드시 venv 경로를 사용해야 함 (시스템 PATH에 없음)

```bash
# 서버 재시작 (기존 프로세스 종료 후 시작) - 이 명령어 사용할 것!
pkill -f "uvicorn main:app" 2>/dev/null; sleep 1; /home/hyeon/project/my_stock/backend/venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000 &

# 서버 상태 확인
curl -s http://localhost:8000/health

# 의존성 설치
cd backend && ./venv/bin/pip install -r requirements.txt

# 테스트 실행
cd backend && ./venv/bin/pytest

# 단일 테스트 파일
cd backend && ./venv/bin/pytest tests/test_ideas.py -v
```

### 프론트엔드 (React + TypeScript + Vite)

```bash
cd frontend && npm install   # 의존성 설치
cd frontend && npm run dev   # 개발 서버 (포트 5173)
cd frontend && npm run build # 프로덕션 빌드
cd frontend && npm run lint  # ESLint
```

### Docker

```bash
docker-compose up -d      # 전체 스택 (db + backend + frontend)
docker-compose up -d db   # DB만 (로컬 개발 시)
```

## 아키텍처

### 요청 흐름

```
Frontend (React) → API Router (api/v1/) → Service → Model/Integration → DB/외부API
                                                  ↑
                                    Scheduler Jobs (백그라운드)
```

### 백엔드 구조

- `main.py` - FastAPI 앱 진입점. lifespan에서 스케줄러 시작, 라우터 등록, CORS 설정
- `api/v1/` - REST API 라우터. 각 파일이 하나의 도메인 담당
- `services/` - 비즈니스 로직. 라우터에서 호출되며 DB 쿼리 + 외부 API 호출 수행
- `models/` - SQLAlchemy ORM 모델 (22개). `Base`를 상속하며 앱 시작 시 `create_all()`로 테이블 생성
- `schemas/` - Pydantic 스키마 (요청/응답 검증)
- `integrations/` - 외부 API 클라이언트 (KIS, DART, YouTube, Naver, Telegram, Gemini, RSS)
- `scheduler/` - APScheduler 기반 백그라운드 작업. `scheduler.py`에서 싱글톤 관리, `jobs/`에 개별 작업
- `core/config.py` - `Settings` 클래스 (pydantic-settings). 환경변수 기반 설정
- `core/database.py` - 동기(`SessionLocal`) + 비동기(`async_session_maker`) 이중 DB 세션

### DB 세션 패턴

동기/비동기 두 가지 DB 세션이 공존:
- **동기**: `get_db()` 의존성 → 대부분의 API 엔드포인트에서 사용
- **비동기**: `get_async_db()` 의존성 → 스케줄러 작업 등 async 컨텍스트에서 사용
- URL 변환: `postgresql://` → `postgresql+asyncpg://` 자동 처리

### 외부 API 연동

- **KIS API**: 한국투자증권 - 주가 조회, OHLCV, 투자자 수급. 토큰 기반 인증, 10req/sec 제한
- **DART API**: 전자공시 조회
- **YouTube Data API**: 채널별 동영상 검색, 종목명 추출
- **Naver Search API**: 뉴스 검색
- **Telegram MTProto**: Telethon 기반 채널 모니터링, 리포트 수집
- **Google Gemini API**: 텔레그램 리포트 감정분석
- **RSS**: 피드 수집 (feedparser)

통합 클라이언트들은 `BaseAPIClient` 추상 클래스를 상속하며 토큰 버킷 rate limiter와 tenacity 기반 자동 재시도를 내장.

### 스케줄러 작업 (Asia/Seoul 타임존)

**장 시간 전용** (월-금 09:00-15:30): `add_market_hours_job()` 사용
- 가격 업데이트 (5분), 알림 체크 (5분)

**정기 간격**: `add_interval_job()` 사용
- 공시 수집 (30분), YouTube (6시간), 텔레그램 모니터링 (5분)
- 텔레그램 리포트 수집 (5분), 감정분석 (30분), 트레이더 동기화 (30분)

**크론**: `add_cron_job()` 사용 (장 마감 후)
- OHLCV (16:40), 차트패턴 (16:30), ETF (16:45), 순환매 알림 (17:00)
- 투자자 수급 (18:30), 신규 아이디어 OHLCV (07:00)
- 텔레그램 아이디어 수집 (4시간마다, 매일)

설정: `coalesce=True` (놓친 작업 1회만), `max_instances=1` (동시 실행 방지)

### 프론트엔드 구조

- `src/App.tsx` - React Router 기반 라우팅 (21개 라우트)
- `src/features/` - 기능별 디렉토리. 각 feature가 페이지 컴포넌트 포함
- `src/services/api.ts` - axios 기반 API 클라이언트. 도메인별 함수 그룹 (ideaApi, priceApi 등)
- `src/store/` - Zustand 상태관리. `useDataStore`(가격/수집 상태), `useIdeaStore`(아이디어 CRUD)
- `src/types/` - TypeScript 타입 정의
- `src/components/` - 공통 UI 컴포넌트. `StockChart`(lightweight-charts), `Layout`(네비게이션/다크모드)
- `src/hooks/useDarkMode.ts` - 시스템 시간 기반 자동 다크모드 전환

스타일링: Tailwind CSS, `darkMode: 'class'` 방식

### 주요 프론트엔드 라우트

`/` 대시보드, `/ideas` 아이디어, `/emerging` 신흥테마, `/themes` 테마순환, `/flow-ranking` 수급랭킹, `/telegram` 텔레그램, `/etf-rotation` ETF순환매, `/sector-flow` 섹터수급, `/pullback` 눌림목, `/trades` 매매분석, `/stocks/:stockCode` 종목상세

## 환경 변수

`backend/.env` 주요 설정:
- `DATABASE_URL` - PostgreSQL 연결 문자열
- `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NO` - 한국투자증권 API
- `YOUTUBE_API_KEY`, `YOUTUBE_CHANNEL_IDS` - YouTube Data API
- `DART_API_KEY` - 전자공시 API
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` - 텔레그램
- `GEMINI_API_KEY` - Google Gemini AI
- `SCHEDULER_ENABLED` - 스케줄러 on/off (기본 true)

## 새 기능 추가 패턴

1. **백엔드**: `models/` 모델 → `schemas/` 스키마 → `services/` 서비스 → `api/v1/` 라우터 → `main.py`에 라우터 등록
2. **프론트엔드**: `types/` 타입 → `services/api.ts`에 API 함수 → `features/` 페이지 컴포넌트 → `App.tsx`에 라우트 추가
3. **스케줄러 작업**: `scheduler/jobs/`에 async 함수 → `scheduler/scheduler.py` `_setup_jobs()`에 등록
