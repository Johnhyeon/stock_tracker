// ── What-If ──────────────────────────────────────────────

export interface WhatIfAlternative {
  rule: string
  triggered: boolean
  exit_date: string | null
  exit_price: number | null
  return_pct: number | null
  diff_pct: number | null
}

export interface WhatIfPosition {
  position_id: string
  stock_code: string
  stock_name: string
  entry_date: string
  exit_date: string
  entry_price: number
  exit_price: number
  actual_return_pct: number
  holding_days: number
  alternatives: WhatIfAlternative[]
}

export interface WhatIfRuleSummary {
  rule: string
  applicable_count: number
  triggered_count: number
  avg_return_pct: number
  total_diff_pct: number
  better_count: number
  worse_count: number
}

export interface WhatIfResponse {
  positions: WhatIfPosition[]
  rule_summaries: WhatIfRuleSummary[]
  actual_avg_return_pct: number
}

// ── Trade Context ────────────────────────────────────────

export interface FlowBar {
  date: string
  foreign_net: number
  institution_net: number
}

export interface RelativeStrengthPoint {
  date: string
  value: number
}

export interface TradeContextResponse {
  position_id: string
  stock_code: string
  stock_name: string
  entry_date: string
  exit_date: string | null
  entry_price: number
  exit_price: number | null
  return_pct: number | null
  ohlcv: Array<{ time: number; open: number; high: number; low: number; close: number; volume: number }>
  trade_markers: Array<{ time: number; type: string; price: number }>
  flow_bars: FlowBar[]
  relative_strength: RelativeStrengthPoint[]
  summary: Record<string, string>
}

// ── Flow Win Rate ────────────────────────────────────────

export interface FlowQuadrant {
  name: string
  label: string
  trade_count: number
  win_count: number
  win_rate: number
  avg_return_pct: number
}

export interface ContraTrade {
  stock_code: string
  stock_name: string
  entry_date: string
  return_pct: number
  foreign_net: number
  institution_net: number
}

export interface FlowWinRateResponse {
  quadrants: FlowQuadrant[]
  contra_trades: ContraTrade[]
  total_trades: number
  flow_available_trades: number
  insight: string
}

// ── Clustering ───────────────────────────────────────────

export interface ClusterTrade {
  stock_code: string
  stock_name: string
  entry_date: string
  return_pct: number
  holding_days: number
}

export interface TradeCluster {
  pattern_key: string
  conditions: Record<string, string>
  trade_count: number
  win_count: number
  win_rate: number
  avg_return_pct: number
  trades: ClusterTrade[]
}

export interface ClusterResponse {
  clusters: TradeCluster[]
  best_pattern: TradeCluster | null
  worst_pattern: TradeCluster | null
  total_clustered: number
  total_positions: number
}
