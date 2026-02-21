/** Catalyst Tracker 타입 */

export interface CatalystEvent {
  id: string
  stock_code: string
  stock_name: string | null
  event_date: string
  catalyst_type: string | null
  title: string
  description: string | null
  price_at_event: number | null
  volume_at_event: number | null
  price_change_pct: number | null
  return_t1: number | null
  return_t5: number | null
  return_t10: number | null
  return_t20: number | null
  current_return: number | null
  max_return: number | null
  max_return_day: number | null
  flow_confirmed: boolean
  flow_score_5d: number | null
  followup_news_count: number
  latest_news_date: string | null
  status: 'active' | 'weakening' | 'expired'
  days_alive: number
  created_at: string
  updated_at: string | null
}

export interface CatalystStats {
  total: number
  active_count: number
  weakening_count: number
  expired_count: number
  by_type: Record<string, {
    count: number
    avg_days: number
    avg_max_return: number
    avg_current_return: number
  }>
}

export interface StockNewsItem {
  id: string
  title: string
  url: string
  source: string | null
  published_at: string
  catalyst_type: string | null
  importance: string | null
  is_quality: boolean
}

export interface CatalystSummary {
  stock_code: string
  days: number
  total_count: number
  type_counts: Record<string, number>
  important_news: {
    title: string
    url: string
    catalyst_type: string | null
    published_at: string
  }[]
}

export interface HotNewsStock {
  stock_code: string
  stock_name: string | null
  news_count: number
  quality_count: number
}

export const CATALYST_TYPE_LABELS: Record<string, string> = {
  policy: '정책/규제',
  earnings: '실적',
  contract: '수주/계약',
  theme: '테마/섹터',
  management: '경영',
  product: '제품/기술',
  other: '기타',
}

export const CATALYST_STATUS_LABELS: Record<string, string> = {
  active: '진행중',
  weakening: '약화',
  expired: '만료',
}

export interface EnrichedCatalystEvent extends CatalystEvent {
  relevance_score: number
  price_context: Array<{
    date: string
    close: number
    volume: number
  }>
}
