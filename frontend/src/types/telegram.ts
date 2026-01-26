/**
 * 텔레그램 모니터링 관련 타입
 */

export interface TelegramChannel {
  id: string
  channel_id: number
  channel_name: string
  channel_username: string | null
  is_enabled: boolean
  last_message_id: number
  created_at: string
  updated_at: string
}

export interface TelegramChannelCreate {
  username?: string
  link?: string
  channel_id?: number
  channel_name?: string
}

export interface TelegramKeywordMatch {
  id: string
  channel_name: string
  message_text: string
  message_date: string
  matched_keyword: string
  stock_code: string | null
  notification_sent: boolean
  created_at: string
}

export interface TelegramMonitorStatus {
  is_configured: boolean
  enabled_channels: number
  active_keywords: number
  recent_matches: number
}

export interface TelegramKeywordList {
  count: number
  keywords: string[]
}

export interface TelegramMonitorCycleResult {
  checked_channels: number
  matches_found: number
  notifications_sent: number
  error?: string
}
