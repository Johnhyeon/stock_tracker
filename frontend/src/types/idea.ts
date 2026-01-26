export type IdeaType = 'research' | 'chart'
export type IdeaStatus = 'active' | 'exited' | 'watching'
export type FundamentalHealth = 'healthy' | 'deteriorating' | 'broken'

export interface InitialPriceInfo {
  price: number
  date: string
}

export interface IdeaMetadata {
  initial_prices?: Record<string, InitialPriceInfo>
  [key: string]: unknown
}

export interface Position {
  id: string
  idea_id?: string
  ticker: string
  stock_name?: string  // 종목명
  entry_price: number
  entry_date?: string  // 대시보드에서는 선택적
  quantity: number
  exit_price?: number
  exit_date?: string
  exit_reason?: string
  days_held: number
  is_open?: boolean
  current_price?: number  // 현재가
  unrealized_profit?: number  // 미실현 손익
  realized_return_pct?: number
  unrealized_return_pct?: number
}

export interface Idea {
  id: string
  created_at: string
  updated_at: string
  type: IdeaType
  sector?: string
  tickers: string[]
  thesis: string
  expected_timeframe_days: number
  target_return_pct: number
  status: IdeaStatus
  fundamental_health: FundamentalHealth
  tags?: string[]
  metadata?: IdeaMetadata
}

export interface IdeaWithPositions extends Idea {
  positions: Position[]
  total_invested?: number
  total_return_pct?: number
}

export interface IdeaCreate {
  type: IdeaType
  sector?: string
  tickers: string[]
  thesis: string
  expected_timeframe_days: number
  target_return_pct: number
  tags?: string[]
  metadata?: IdeaMetadata
  created_at?: string  // 과거 날짜로 생성 시 (ISO 8601 형식)
}

export interface IdeaUpdate {
  sector?: string
  tickers?: string[]
  thesis?: string
  expected_timeframe_days?: number
  target_return_pct?: number
  status?: IdeaStatus
  fundamental_health?: FundamentalHealth
  tags?: string[]
}

export interface PositionCreate {
  ticker: string
  entry_price: number
  quantity: number
  entry_date?: string
  notes?: string
}

export interface PositionExit {
  exit_price: number
  exit_date?: string
  exit_reason?: string
}

export interface PositionAddBuy {
  price: number
  quantity: number
  buy_date?: string
}

export interface PositionPartialExit {
  exit_price: number
  quantity: number
  exit_date?: string
  exit_reason?: string
}

export interface ExitCheckResult {
  should_exit: boolean
  reasons: {
    fundamental_broken: boolean
    time_expired: boolean
    fundamental_deteriorating: boolean
  }
  warnings: string[]
  fomo_stats?: {
    count: number
    avg_return_at_exit?: number
    message?: string
  }
}

export interface DashboardStats {
  total_ideas: number
  active_ideas: number
  watching_ideas: number
  research_ideas: number
  chart_ideas: number
  total_invested: number
  total_unrealized_return: number
  avg_return_pct?: number
}

export interface IdeaSummary extends Idea {
  positions: Position[]
  total_invested: number
  total_unrealized_return_pct?: number
  days_active: number
  time_remaining_days: number
}

export interface DashboardData {
  stats: DashboardStats
  research_ideas: IdeaSummary[]
  chart_ideas: IdeaSummary[]
  watching_ideas: IdeaSummary[]
}

export interface TimelineEntry {
  idea_id: string
  idea_type: IdeaType
  ticker: string
  entry_date: string
  exit_date?: string
  days_held: number
  expected_days: number
  time_diff_days: number
  return_pct?: number
  exit_reason?: string
}

export interface TimelineAnalysis {
  entries: TimelineEntry[]
  avg_time_diff: number
  early_exits: number
  on_time_exits: number
  late_exits: number
}

export interface FomoExit {
  idea_id: string
  ticker: string
  exit_date: string
  exit_return_pct: number
  days_after_exit: number
  price_after_exit?: number
  missed_return_pct?: number
}

export interface FomoAnalysis {
  fomo_exits: FomoExit[]
  total_fomo_exits: number
  avg_missed_return_pct?: number
  total_missed_opportunity?: number
  summary: {
    message: string
    recommendation?: string
  }
}
