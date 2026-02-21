export interface SmartScoreBadge {
  composite_score: number
  composite_grade: string
  chart_grade: string
  narrative_grade: string
  flow_grade: string
  social_grade: string
}

export interface PortfolioPosition {
  id: string
  ticker: string
  stock_code?: string
  stock_name?: string
  entry_price: number
  entry_date?: string
  quantity: number
  days_held: number
  current_price?: number
  unrealized_profit?: number
  unrealized_return_pct?: number
  invested?: number
  smart_score?: SmartScoreBadge
  price_trend_7d: number[]
}

export interface PortfolioIdea {
  id: string
  type: string
  sector?: string
  tickers: string[]
  thesis: string
  status: string
  fundamental_health: string
  expected_timeframe_days: number
  target_return_pct: number
  created_at: string
  positions: PortfolioPosition[]
  total_invested: number
  total_eval?: number
  total_unrealized_profit?: number
  total_unrealized_return_pct?: number
  days_active: number
  time_remaining_days: number
}

export interface PortfolioTrendPoint {
  date: string
  total_invested: number
  total_eval: number
  unrealized_profit: number
  return_pct: number
}

export interface PerformerInfo {
  stock_code: string
  stock_name: string
  return_pct: number
}

export interface PortfolioStats {
  total_ideas: number
  active_ideas: number
  watching_ideas: number
  total_invested: number
  total_eval?: number
  total_unrealized_profit?: number
  total_return_pct?: number
  avg_return_pct?: number
  best_performer?: PerformerInfo
  worst_performer?: PerformerInfo
}

export interface PortfolioDashboardData {
  stats: PortfolioStats
  active_ideas: PortfolioIdea[]
  watching_ideas: PortfolioIdea[]
  portfolio_trend: PortfolioTrendPoint[]
}
