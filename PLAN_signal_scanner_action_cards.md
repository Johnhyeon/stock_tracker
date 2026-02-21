# Signal Scanner 액션 카드/라벨 개발 계획

작성일: 2026-02-21  
프로젝트: `D:\project\stock_tracker`

---

## 0) 목표

현재 스캐너는 **분석 정보는 풍부**하지만, 사용자 입장에서 마지막 질문인
> "그래서 오늘 뭘 해야 하지?"
에 대한 답이 약함.

이번 작업 목표:
1. 상단 `오늘의 액션` 카드 추가
   - 매수 검토
   - 눌림 대기(관찰)
   - 제외
2. 각 종목 행에 액션 라벨 추가
   - 매수검토 / 관찰 / 제외

---

## 1) 구현 방향 (권장)

### 백엔드에서 액션을 계산하고 프론트는 표시만 수행

이유:
- 규칙 변경 시 프론트/백엔드 불일치 방지
- API/백테스트/리포트 재활용 가능
- 향후 알림(텔레그램/푸시) 연계 쉬움

---

## 2) 액션 분류 규칙 v1 (초안)

> 운영하면서 조정 가능한 초기 버전

### A. 매수검토
아래 조건을 모두 만족하면 `매수검토`
- `grade == "A"`
- `total_score >= 78`
- `abcd_phase in ["C", "D"]`
- `ma_alignment == "bullish"`
- `ma20_distance_pct`가 `-3% ~ +3%` 범위 (너무 이격된 추격 방지)
- `has_kkandolji == true` 또는 `volume_ratio >= 1.2`

### B. 관찰(눌림 대기)
아래 중 하나라도 만족하면 `관찰`
- `grade in ["A", "B"]` and `abcd_phase in ["B", "C"]`
- `grade == "A"` but `ma20_distance_pct > 3%` (추격 위험)
- `ma_alignment == "mixed"` but `total_score >= 70`

### C. 제외
- 위 조건 미충족 전체

### D. 이유 문구(tooltip/보조텍스트)
- 예: `"A등급+C구간+정배열, MA20 근접"`
- 예: `"B구간 진행 중, 눌림 재확인 필요"`
- 예: `"점수/배열 기준 미달"`

---

## 3) 변경 파일

## 백엔드
1. `backend/schemas/signal_scanner.py`
   - `ScannerAction` enum 추가 (`buy_review`, `watch`, `exclude`)
   - `ScannerSignal`에 필드 추가
     - `action: ScannerAction`
     - `action_label: str`
     - `action_reason: str`

2. `backend/services/signal_scanner_service.py`
   - `_classify_action(...)` 함수 추가
   - `_analyze_single(...)`에서 액션 계산/주입

3. (선택) `backend/api/v1/signal_scanner.py`
   - 별도 요약 API 추가
     - `GET /signal-scanner/signals/summary`
     - 응답: `{ buy_review, watch, exclude, total }`
   - 단, 초기에는 프론트에서 기존 `signals` 응답 집계해도 충분

## 프론트엔드
1. `frontend/src/services/api.ts`
   - `ScannerSignal` 타입에 신규 필드 반영
     - `action`, `action_label`, `action_reason`

2. `frontend/src/features/signal-scanner/SignalScannerPage.tsx`
   - 상단 액션 카드 UI 추가 (필터 적용 결과 기준 집계)
   - 테이블 컬럼 추가: `액션`
   - 액션 배지 색상 매핑
     - 매수검토: red/orange 계열
     - 관찰: blue/yellow 계열
     - 제외: gray 계열
   - 기존 점수/등급 옆에 액션 우선 노출

3. (선택) 컴포넌트 분리
   - `frontend/src/features/signal-scanner/components/ActionSummaryCards.tsx`
   - `frontend/src/features/signal-scanner/components/ActionBadge.tsx`

---

## 4) UX 상세

### 상단 카드 배치
- 기존 `ABCD 통계` 위 또는 아래에 3카드 배치
- 카드 클릭 시 즉시 필터링
  - 매수검토 클릭 → 해당 액션 종목만
  - 관찰 클릭 → 관찰만
  - 제외 클릭 → 제외만

### 테이블 액션 컬럼
- 신규 컬럼: `액션`
- 배지 + 툴팁(reason)

예시:
- `매수검토` (툴팁: `A등급/C구간/정배열/MA20근접`)
- `관찰` (툴팁: `B구간 진행, 눌림 재확인 필요`)
- `제외` (툴팁: `점수 기준 미달`)

---

## 5) 단계별 일정 (현실적)

### Phase 1 (0.5일)
- 백엔드 enum/필드 추가
- 서비스 액션 분류 함수 반영
- API 응답 확인

### Phase 2 (0.5일)
- 프론트 타입 반영
- 상단 카드 + 액션 컬럼 UI 반영
- 카드 필터 동작

### Phase 3 (0.5일)
- 액션 기준 튜닝
- reason 문구 다듬기
- 버그/예외 처리

총 1.5일 내 첫 배포 가능

---

## 6) 검증 체크리스트

- [ ] `/signal-scanner/signals` 응답에 `action/action_label/action_reason` 존재
- [ ] 상단 카드 합계 == 현재 필터 결과 종목 수
- [ ] `min_score`, `관심종목`, `실전패턴` 필터와 액션 카드 동시 동작
- [ ] 다크모드 색상 가독성 확보
- [ ] 모바일/작은 해상도에서 카드 줄바꿈 깨짐 없음

---

## 7) 리스크 및 대응

1. **규칙 과도 단순화 리스크**
   - 대응: 초기 버전은 보수적(매수검토 적게)으로 운영
2. **사용자 오해(추천 보장)**
   - 대응: 라벨 근처에 `투자판단 본인책임` 고지
3. **MDD 등 기존 지표 신뢰 이슈**
   - 대응: 매매분석 페이지 계산식 별도 점검(우선순위 높음)

---

## 8) 다음 확장 (v2)

- 액션별 과거 성과 추적 (매수검토 승률, 관찰 후 전환율)
- 사용자별 커스텀 룰(임계치 슬라이더)
- 알림 연동: `매수검토 N개 발생 시 텔레그램 요약`

---

## 최종 한 줄 포지셔닝 (서비스 문구)

**"매일 장 마감 후, 200개 후보를 매수 검토 10개로 줄여주는 의사결정 도구"**
