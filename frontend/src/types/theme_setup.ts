// Theme Setup Types - 테마 셋업 (자리 잡는 테마 감지)

export interface TopPatternStock {
  code: string
  name: string
  pattern: string
  confidence: number
}

export interface ThemeSetup {
  theme_name: string
  rank: number
  total_score: number
  news_momentum_score: number
  chart_pattern_score: number
  mention_score: number
  price_action_score: number
  investor_flow_score: number
  top_stocks: TopPatternStock[]
  stocks_with_pattern: number
  total_stocks: number
  is_emerging: number
  explanation?: string  // 점수 산출 이유 설명
  score_breakdown?: ScoreBreakdown
}

export interface ScoreBreakdown {
  news: {
    score: number
    '7d_count'?: number
    wow_change?: number
    source_diversity?: number
  }
  chart: {
    score: number
    pattern_ratio?: number
    avg_confidence?: number
    patterns?: string[]
    pattern_count?: number
    total_stocks?: number
  }
  mention: {
    score: number
    youtube_count?: number
    expert_count?: number
  }
  price: {
    score: number
    avg_change?: number
    volume_change?: number
  }
  flow?: {
    score: number
    foreign_net_sum?: number
    institution_net_sum?: number
    positive_foreign?: number
    positive_institution?: number
    total_stocks?: number
    avg_flow_score?: number
  }
}

export interface ThemeSetupHistory {
  date: string
  score: number
  rank: number
}

export interface ThemeSetupDetail extends ThemeSetup {
  score_breakdown: ScoreBreakdown
  setup_date: string
  history: ThemeSetupHistory[]
}

export interface ChartPattern {
  stock_code: string
  stock_name: string
  pattern_type: string
  confidence: number
  pattern_data: Record<string, unknown>
  current_price: number
  price_from_support_pct?: number
  price_from_resistance_pct?: number
}

export interface NewsTrendItem {
  date: string
  mention_count: number
  unique_sources: number
  top_keywords: Array<{ keyword: string; count: number }>
  wow_change_pct?: number
}

export interface ThemeNewsItem {
  title: string
  url: string
  source: string
  published_at: string
  keyword: string
}

export interface EmergingThemesResponse {
  themes: ThemeSetup[]
  total_count: number
  generated_at: string
}

export interface SetupHistoryItem {
  date: string
  total_score: number
  news_score: number
  chart_score: number
  mention_score: number
  price_score: number
  flow_score: number
  rank: number
}

// 패턴 타입 한글 매핑
export const PATTERN_TYPE_LABELS: Record<string, string> = {
  range_bound: '횡보/박스권',
  double_bottom: '쌍바닥',
  triple_bottom: '삼중바닥',
  converging: '수렴',
  pre_breakout: '돌파 직전',
}

// 패턴별 색상
export const PATTERN_TYPE_COLORS: Record<string, string> = {
  range_bound: 'bg-gray-100 text-gray-800',
  double_bottom: 'bg-green-100 text-green-800',
  triple_bottom: 'bg-emerald-100 text-emerald-800',
  converging: 'bg-blue-100 text-blue-800',
  pre_breakout: 'bg-orange-100 text-orange-800',
}
