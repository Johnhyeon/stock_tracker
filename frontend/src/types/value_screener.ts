export interface ValueMetrics {
  stock_code: string
  stock_name: string
  sector: string | null
  current_price: number | null
  per: number | null
  pbr: number | null
  roe: number | null
  roa: number | null
  operating_margin: number | null
  net_margin: number | null
  debt_ratio: number | null
  current_ratio: number | null
  revenue_growth: number | null
  per_score: number
  pbr_score: number
  roe_score: number
  margin_score: number
  growth_score: number
  safety_score: number
  total_score: number
  grade: 'A' | 'B' | 'C' | 'D'
  comment: string
  fair_value: number | null
  upside_pct: number | null
  valuation_method: string | null
  bsns_year: string | null
  reprt_code: string | null
}

export interface ValueScreenerSummary {
  grade_counts: Record<string, number>
  avg_per: number | null
  avg_pbr: number | null
  avg_roe: number | null
  total_screened: number
}

export interface ValueScreenerResponse {
  stocks: ValueMetrics[]
  summary: ValueScreenerSummary
  generated_at: string
}
