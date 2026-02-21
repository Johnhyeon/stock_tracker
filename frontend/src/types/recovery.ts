/** 장중 갭다운 회복 분석 타입 */

export interface GapRecoveryStock {
  stock_code: string
  stock_name: string
  themes: string[]

  prev_close: number
  open_price: number
  current_price: number
  high_price: number
  low_price: number
  volume: number

  gap_pct: number               // 시가 갭 (음수 = 갭다운)
  change_from_open_pct: number  // 시가 대비 현재 변동률

  gap_fill_pct: number          // 갭 메움 비율 (100=완전 메움)
  recovery_from_low_pct: number // 저가 대비 회복률
  is_above_prev_close: boolean  // 전일종가 상회 여부

  recovery_score: number
}

export interface GapRecoveryResponse {
  stocks: GapRecoveryStock[]
  count: number
  total_gap_down: number
  total_scanned: number
  market_status: 'open' | 'closed'
  min_gap_pct: number
  generated_at: string
  message?: string  // 첫 스캔 진행중 메시지
}
