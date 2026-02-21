export interface IntelFeedItem {
  signal_type: 'catalyst' | 'flow_spike' | 'chart_pattern' | 'emerging_theme' | 'youtube' | 'convergence' | 'telegram'
  severity: 'critical' | 'high' | 'medium' | 'info'
  stock_code?: string
  stock_name?: string
  title: string
  description: string
  timestamp: string
  metadata: Record<string, any>
}

export interface IntelSummary {
  catalyst: number
  flow_spike: number
  chart_pattern: number
  emerging_theme: number
  youtube: number
  convergence: number
  telegram: number
  total: number
  critical_count: number
  high_count: number
}

export interface MarketIntelData {
  feed: IntelFeedItem[]
  summary: IntelSummary
  generated_at: string
}
