export interface SmartSignalDimension {
  score: number
  max_score: number
  grade: string
  details: Record<string, number>
}

export interface SmartScannerStock {
  stock_code: string
  stock_name: string
  themes: string[]
  current_price: number
  composite_score: number
  composite_grade: string
  chart: SmartSignalDimension
  narrative: SmartSignalDimension
  flow: SmartSignalDimension
  social: SmartSignalDimension
  signal_type: string | null
  aligned_count: number
  expert_mention_count: number
  youtube_count: number
  telegram_count: number
  news_count_7d: number
  disclosure_count_30d: number
  foreign_net_5d: number
  institution_net_5d: number
  consecutive_foreign_buy: number
  sentiment_avg: number
  change_rate: number | null
  volume_ratio: number | null
  ma20_distance_pct: number | null
}

export interface SmartScannerResponse {
  stocks: SmartScannerStock[]
  count: number
  summary: {
    grade_counts: Record<string, number>
    aligned_3_plus: number
  }
  generated_at: string
}

export interface NarrativeBriefing {
  stock_code: string
  stock_name: string
  one_liner: string
  why_moving: string
  theme_context: string
  expert_perspective: string
  financial_highlight: string
  catalysts: string[]
  risk_factors: string[]
  narrative_strength: string
  market_outlook: string
  generated_at: string
}
