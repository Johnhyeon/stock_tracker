/**
 * 텔레그램 아이디어 타입 정의
 */

export type IdeaSourceType = 'my' | 'others'

export interface TelegramIdea {
  id: string
  created_at: string

  // 채널 정보
  channel_id: number
  channel_name: string
  source_type: IdeaSourceType

  // 메시지 정보
  message_id: number
  message_text: string
  original_date: string

  // 포워딩 정보
  is_forwarded: boolean
  forward_from_name: string | null

  // 종목 정보
  stock_code: string | null
  stock_name: string | null

  // 분석 데이터
  sentiment: 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL' | null
  sentiment_score: number | null

  // 메타데이터
  raw_hashtags: string[]
}

export interface TelegramIdeaListResponse {
  items: TelegramIdea[]
  total: number
  offset: number
  limit: number
}

export interface StockMentionStats {
  stock_code: string
  stock_name: string
  mention_count: number
  latest_date: string
  sources: IdeaSourceType[]
}

export interface StockStatsResponse {
  stocks: StockMentionStats[]
  total_count: number
}

export interface AuthorStockInfo {
  stock_code: string
  stock_name: string
  count: number
}

export interface AuthorStats {
  name: string
  idea_count: number
  top_stocks: AuthorStockInfo[]
  latest_idea_date: string
}

export interface AuthorStatsResponse {
  authors: AuthorStats[]
  total_count: number
}

export interface TelegramIdeaCollectResult {
  channel_name: string
  messages_collected: number
  ideas_created: number
  errors: string[]
}

export interface TelegramIdeaCollectResponse {
  results: TelegramIdeaCollectResult[]
  total_messages: number
  total_ideas: number
}
