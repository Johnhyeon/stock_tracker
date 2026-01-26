// Data API Types

export interface PriceData {
  stock_code: string
  stock_name: string
  current_price: number
  change: number
  change_rate: number
  volume: number
  high_price: number
  low_price: number
  open_price: number
  prev_close: number
  market_cap?: number
  updated_at: string
}

export interface OHLCVItem {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  change?: number
  change_rate?: number
}

export interface OHLCVData {
  stock_code: string
  period: 'D' | 'W' | 'M'
  data: OHLCVItem[]
}

// Disclosure Types

export type DisclosureType = 'regular' | 'fair' | 'material' | 'external_audit' | 'other'
export type DisclosureImportance = 'high' | 'medium' | 'low'

export interface Disclosure {
  id: string
  created_at: string
  rcept_no: string
  rcept_dt: string
  corp_code: string
  corp_name: string
  stock_code?: string
  report_nm: string
  flr_nm?: string
  disclosure_type: DisclosureType
  importance: DisclosureImportance
  summary?: string
  is_read: boolean
  url?: string
}

export interface DisclosureListResponse {
  items: Disclosure[]
  total: number
  skip: number
  limit: number
}

export interface DisclosureStats {
  total: number
  unread: number
  by_importance: Record<string, number>
  by_type: Record<string, number>
}

export interface DisclosureCollectRequest {
  bgn_de?: string
  end_de?: string
  stock_codes?: string[]
  min_importance?: DisclosureImportance
}

export interface DisclosureCollectResponse {
  collected: number
  new: number
  skipped: number
}

// YouTube Types

export interface YouTubeMention {
  id: string
  created_at: string
  video_id: string
  video_title: string
  channel_id: string
  channel_name?: string
  published_at: string
  view_count?: number
  like_count?: number
  comment_count?: number
  duration?: string
  mentioned_tickers: string[]
  ticker_context?: string
  thumbnail_url?: string
}

export interface YouTubeMentionListResponse {
  items: YouTubeMention[]
  total: number
  skip: number
  limit: number
}

export interface TrendingTicker {
  stock_code: string
  stock_name?: string
  mention_count: number
  total_views: number
}

export interface TickerMentionHistory {
  date: string
  mention_count: number
  total_views: number
}

export interface YouTubeCollectResponse {
  collected: number
  new: number
  with_mentions: number
  tickers_searched: string[]
}

export interface HotCollectResponse {
  collected: number
  new: number
  with_mentions: number
  tickers_found: string[]
  mode: 'quick' | 'normal' | 'full'
}

export type CollectMode = 'quick' | 'normal' | 'full'

export interface ScoreBreakdown {
  mention_growth: number    // 언급 증가율 (25점 만점)
  mention_volume: number    // 절대 언급량 (15점 만점)
  view_weight: number       // 조회수 가중치 (10점 만점)
  price_momentum: number    // 주가 모멘텀 (20점 만점)
  volume_score: number      // 거래량 (20점 만점)
  new_bonus: number         // 신규 등장 보너스 (10점)
  is_contrarian: boolean    // 역발상 매수 시그널 여부
}

export interface RisingTicker {
  stock_code: string
  stock_name: string | null
  recent_mentions: number
  prev_mentions: number
  growth_rate: number
  total_views: number
  is_new: boolean
  // KIS API 데이터
  current_price?: number | null
  price_change?: number | null
  price_change_rate?: number | null
  volume?: number | null
  volume_ratio?: number | null
  // 가중치 점수
  weighted_score?: number | null
  score_breakdown?: ScoreBreakdown | null
}

// Scheduler Types

export interface SchedulerJob {
  id: string
  name: string
  next_run_time?: string
  trigger: string
}

export interface SchedulerStatus {
  running: boolean
  jobs: SchedulerJob[]
}

// Health Check Types

export interface APIHealthStatus {
  configured: boolean
  connected: boolean
  error?: string | null
}

export interface AllAPIHealthStatus {
  kis: APIHealthStatus
  dart: APIHealthStatus
  youtube: APIHealthStatus
}

// Alert Types

export type AlertType =
  | 'youtube_surge'
  | 'disclosure_important'
  | 'fomo_warning'
  | 'target_reached'
  | 'fundamental_deterioration'
  | 'time_expired'
  | 'trader_new_mention'
  | 'trader_cross_check'
  | 'custom'

export type NotificationChannel = 'telegram' | 'email' | 'both'

export interface AlertRule {
  id: string
  created_at: string
  updated_at: string
  name: string
  description?: string
  alert_type: AlertType
  channel: NotificationChannel
  is_enabled: boolean
  conditions: Record<string, unknown>
  cooldown_minutes: number
  last_triggered_at?: string
}

export interface NotificationLog {
  id: string
  created_at: string
  alert_rule_id?: string
  alert_type: AlertType
  channel: NotificationChannel
  recipient?: string
  title: string
  message: string
  is_success: boolean
  error_message?: string
  related_entity_type?: string
  related_entity_id?: string
}

export interface AlertSettings {
  telegram_configured: boolean
  telegram_bot_username?: string
  email_configured: boolean
  smtp_host?: string
  total_rules: number
  enabled_rules: number
}

export interface TestNotificationRequest {
  channel: NotificationChannel
  recipient?: string
  title?: string
  message?: string
}

export interface TestNotificationResponse {
  success: boolean
  channel: NotificationChannel
  message: string
  error?: string
}

// Position Bulk Types

export interface ParsedPosition {
  stock_code?: string
  stock_name?: string
  quantity?: number
  avg_price?: number
  current_price?: number
  profit_loss?: number
  profit_loss_rate?: number
  raw_text: string
  is_valid: boolean
  error?: string
}

export interface ParseResult {
  total: number
  valid: number
  invalid: number
  positions: ParsedPosition[]
}

export interface BulkCreateResult {
  total: number
  created: number
  failed: number
  errors: string[]
  created_position_ids: string[]
}

export interface FileImportResult {
  total: number
  success: number
  failed: number
  positions: ParsedPosition[]
  errors: string[]
}

// Trader Watchlist Types

export interface TraderHotStock {
  stock_name: string
  stock_code: string | null
  mention_count: number
  first_mention_date: string
  last_mention_date: string
  is_new: boolean
  // KIS API 데이터
  current_price: number | null
  price_change: number | null
  price_change_rate: number | null
  volume: number | null
  // 성과
  avg_mention_change: number | null
  performance_since_first: number | null
  // 가중치 점수
  weighted_score: number | null
}

export interface TraderRisingStock {
  stock_name: string
  stock_code: string | null
  recent_mentions: number
  prev_mentions: number
  growth_rate: number
  is_new: boolean
  // KIS API 데이터
  current_price: number | null
  price_change_rate: number | null
  volume: number | null
  // 가중치 점수
  weighted_score: number | null
}

export interface TraderPerformanceStats {
  total_stocks: number
  avg_performance: number
  win_rate: number
  best_stock: string | null
  best_performance: number | null
  worst_stock: string | null
  worst_performance: number | null
  // 기간별 성과
  performance_1d: number | null
  performance_3d: number | null
  performance_7d: number | null
  performance_14d: number | null
}

export interface TraderSyncResponse {
  total_stocks: number
  total_mentions: number
  new_mentions: number
  updated_stocks: number
}

export interface TraderNewMention {
  stock_name: string
  stock_code: string | null
  mention_date: string
  change_rate: number | null
  source_link: string | null
}

export interface TraderCrossCheck {
  stock_name: string
  stock_code: string
  idea_title: string
  trader_mention_count: number
  last_mentioned: string
}

// Theme Rotation Types

export interface ThemeStock {
  code: string
  name: string | null
  source?: string // youtube, trader, both
  mentions: number
  price_change: number | null
  volume: number | null
}

export interface HotTheme {
  theme_name: string
  total_score: number
  stock_count: number
  youtube_mentions: number
  trader_mentions: number
  avg_price_change: number
  total_volume: number
  stocks: ThemeStock[]
}

export interface ThemeSummary {
  total_themes_detected: number
  top_theme: string | null
  avg_theme_score: number
}

export interface ThemeRotationResponse {
  hot_themes: HotTheme[]
  theme_count: number
  categories: Record<string, HotTheme[]>
  analyzed_at: string
  summary: ThemeSummary
}

export interface ThemeListItem {
  name: string
  stock_count: number
}

export interface ThemeSearchResult {
  name: string
  stock_count: number
  stocks: Array<{ code: string; name: string }>
}

export interface StockThemesResponse {
  stock_code: string
  themes: string[]
  theme_count: number
}
