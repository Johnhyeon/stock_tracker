export interface TopStock {
  code: string
  name: string
  news_count: number
}

export interface ThemePulseItem {
  rank: number
  theme_name: string
  news_count: number
  high_importance_count: number
  momentum: number
  catalyst_types: Record<string, number>
  top_stocks: TopStock[]
  setup_score: number
  setup_rank: number | null
}

export interface ThemePulseResponse {
  items: ThemePulseItem[]
  total_themes: number
  total_news: number
  period_days: number
  generated_at: string
}

export interface TimelineDataPoint {
  date: string
  count: number
}

export interface TimelineTheme {
  name: string
  data: TimelineDataPoint[]
}

export interface TimelineResponse {
  dates: string[]
  themes: TimelineTheme[]
  generated_at: string
}

export interface CatalystDistItem {
  type: string
  count: number
  ratio: number
}

export interface ImportanceDistItem {
  level: string
  count: number
  ratio: number
}

export interface CatalystDistributionResponse {
  catalyst_distribution: CatalystDistItem[]
  importance_distribution: ImportanceDistItem[]
  total_news: number
  period_days: number
  generated_at: string
}
