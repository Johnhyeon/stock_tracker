/**
 * 통합 데이터 상태 타입 정의
 */

// 데이터 카테고리
export type DataCategory = 'market' | 'analysis' | 'external' | 'telegram'

// 데이터 상태
export type DataStatus = 'ok' | 'stale' | 'empty' | 'error' | 'unknown'

// 스케줄 정보
export interface ScheduleInfo {
  description: string  // "매일 16:40", "6시간마다" 등
  next_run: string | null  // 다음 실행 예정 시간 (ISO string)
  is_market_hours_only: boolean  // 장중만 실행 여부
}

// 확장된 데이터 상태 항목
export interface DataStatusItemFull {
  key: string  // 데이터 타입 키
  name: string  // 표시 이름
  category: DataCategory  // 카테고리
  last_updated: string | null  // 마지막 업데이트 시간 (ISO string)
  record_count: number  // 레코드 수
  is_stale: boolean  // 오래된 데이터 여부
  status: DataStatus  // 상태
  schedule: ScheduleInfo  // 스케줄 정보
  can_refresh: boolean  // 수동 새로고침 가능 여부
}

// 전체 데이터 상태 응답 (카테고리별 그룹화)
export interface AllDataStatusResponse {
  market: DataStatusItemFull[]  // 시세 데이터
  analysis: DataStatusItemFull[]  // 분석 데이터
  external: DataStatusItemFull[]  // 외부 소스
  telegram: DataStatusItemFull[]  // 텔레그램
  overall_status: 'ok' | 'needs_refresh' | 'critical'  // 전체 상태
  checked_at: string  // 확인 시간 (ISO string)
}

// 카테고리 정보
export interface CategoryInfo {
  key: DataCategory
  name: string
  icon: string
  items: DataStatusItemFull[]
}

// 카테고리 메타데이터
export const CATEGORY_META: Record<DataCategory, { name: string; icon: string }> = {
  market: { name: '시세 데이터', icon: '📈' },
  analysis: { name: '분석 데이터', icon: '📊' },
  external: { name: '외부 소스', icon: '🌐' },
  telegram: { name: '텔레그램', icon: '💬' },
}

// 상태 색상 (라이트모드)
export const STATUS_COLORS: Record<DataStatus, string> = {
  ok: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  stale: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  empty: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  error: 'bg-gray-100 text-gray-500 dark:bg-t-bg-card dark:text-t-text-muted',
  unknown: 'bg-gray-100 text-gray-400 dark:bg-t-bg-card dark:text-t-text-muted',
}

// 상태 텍스트
export const STATUS_TEXT: Record<DataStatus, string> = {
  ok: '최신',
  stale: '오래됨',
  empty: '데이터 없음',
  error: '오류',
  unknown: '확인 중',
}

// 상태 도트 색상
export const STATUS_DOT_COLORS: Record<DataStatus, string> = {
  ok: 'bg-green-500',
  stale: 'bg-yellow-500',
  empty: 'bg-red-500',
  error: 'bg-gray-400',
  unknown: 'bg-gray-300',
}
