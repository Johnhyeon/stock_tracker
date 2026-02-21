export interface EntryTimingItem {
  trade_date: string
  stock_code: string
  stock_name: string
  price: number
  ma20_pct: number | null
  ma60_pct: number | null
  bb_position: number | null
  high20_pct: number | null
  volume_ratio: number | null
}

export interface EntryTimingSummary {
  total_entries: number
  above_ma20_pct: number
  above_ma60_pct: number
  avg_ma20_pct: number
  avg_ma60_pct: number
  bb_lower_pct: number
  bb_middle_pct: number
  bb_upper_pct: number
  avg_volume_ratio: number
  high_volume_pct: number
  items: EntryTimingItem[]
}

export interface ExitTimingItem {
  trade_date: string
  stock_code: string
  stock_name: string
  price: number
  realized_return_pct: number | null
  after_5d_pct: number | null
  after_10d_pct: number | null
  after_20d_pct: number | null
  peak_vs_exit_pct: number | null
}

export interface ExitTimingSummary {
  total_exits: number
  avg_after_5d: number
  avg_after_10d: number
  avg_after_20d: number
  early_sell_pct: number
  good_sell_pct: number
  avg_peak_vs_exit: number
  items: ExitTimingItem[]
}

export interface MFEMAEItem {
  stock_code: string
  stock_name: string
  entry_price: number
  exit_price: number
  entry_date: string
  exit_date: string
  realized_return_pct: number
  mfe_pct: number
  mae_pct: number
  capture_ratio: number | null
}

export interface ScatterPoint {
  x: number
  y: number
  stock_name: string
  is_winner: boolean
}

export interface MFEMAESummary {
  total_positions: number
  avg_mfe: number
  avg_mae: number
  avg_capture_ratio: number
  scatter_data: ScatterPoint[]
  items: MFEMAEItem[]
}

export interface MiniChartCandle {
  time: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface TradeMarkerData {
  time: number
  type: string
  price: number
}

export interface MiniChartData {
  stock_code: string
  stock_name: string
  trade_type: string
  trade_date: string
  price: number
  realized_return_pct: number | null
  candles: MiniChartCandle[]
  markers: TradeMarkerData[]
}

export interface ChartAnalysisResponse {
  entry_timing: EntryTimingSummary
  exit_timing: ExitTimingSummary
  mfe_mae: MFEMAESummary
  mini_charts: MiniChartData[]
  worst_mini_charts: MiniChartData[]
}
