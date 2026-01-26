# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

한국 주식 투자 아이디어 추적 및 분석 시스템. YouTube 언급량, KIS 주가/거래량, 공시 정보를 결합하여 투자 시그널을 제공합니다.

## 개발 명령어

### 백엔드 (FastAPI + PostgreSQL)

```bash
# 의존성 설치
cd backend && pip install -r requirements.txt

# 로컬 서버 실행
cd backend && uvicorn main:app --reload --port 8000

# 테스트 실행
cd backend && pytest

# 단일 테스트 파일
cd backend && pytest tests/test_ideas.py -v

# 특정 테스트 함수
cd backend && pytest tests/test_ideas.py::test_create_idea -v
```

### 프론트엔드 (React + TypeScript + Vite)

```bash
# 의존성 설치
cd frontend && npm install

# 개발 서버
cd frontend && npm run dev

# 빌드
cd frontend && npm run build

# 린트
cd frontend && npm run lint
```

### Docker

```bash
# 전체 스택 실행
docker-compose up -d

# DB만 실행 (로컬 개발 시)
docker-compose up -d db
```

## 아키텍처

### 백엔드 구조

- `main.py` - FastAPI 앱 진입점, lifespan에서 스케줄러 시작
- `api/v1/` - REST API 엔드포인트 (ideas, positions, youtube, themes, alerts 등)
- `services/` - 비즈니스 로직 (youtube_service, alert_service, theme_service 등)
- `models/` - SQLAlchemy ORM 모델
- `schemas/` - Pydantic 스키마 (요청/응답)
- `integrations/` - 외부 API 클라이언트 (KIS, DART, YouTube, Naver, Telegram)
- `scheduler/` - APScheduler 기반 백그라운드 작업 (가격 업데이트, 공시 수집 등)
- `core/config.py` - 환경변수 설정 (Settings 클래스)
- `core/database.py` - DB 연결 (동기/비동기 세션)

### 프론트엔드 구조

- `src/features/` - 기능별 컴포넌트 (ideas, positions, themes, youtube, alerts 등)
- `src/services/` - API 클라이언트
- `src/store/` - Zustand 상태 관리
- `src/types/` - TypeScript 타입 정의

### 외부 API 연동

- **KIS API**: 한국투자증권 - 주가 조회, OHLCV, 투자자 수급
- **DART API**: 전자공시 조회
- **YouTube Data API**: 채널별 동영상 검색, 언급 종목 추출
- **Naver Search API**: 뉴스 검색

### 스케줄러 작업

장 시간(월-금 09:00-15:30) 및 정기 시간에 자동 실행:
- 가격 업데이트 (5분 간격, 장 시간)
- 공시 수집 (30분 간격)
- YouTube 수집 (6시간 간격)
- OHLCV 수집 (16:40, 장 마감 후)
- 투자자 수급 수집 (18:30)

## 환경 변수

`backend/.env` 필수 설정:
- `DATABASE_URL` - PostgreSQL 연결 문자열
- `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NO` - 한국투자증권 API
- `YOUTUBE_API_KEY`, `YOUTUBE_CHANNEL_IDS` - YouTube Data API
- `DART_API_KEY` - 전자공시 API

## API 엔드포인트 패턴

- `/api/v1/ideas` - 투자 아이디어 CRUD
- `/api/v1/positions` - 포지션 관리
- `/api/v1/youtube` - YouTube 언급 분석
- `/api/v1/themes` - 테마 분석
- `/api/v1/alerts` - 알림 설정
- `/api/v1/stocks` - 종목 정보
- `/health` - 헬스체크
