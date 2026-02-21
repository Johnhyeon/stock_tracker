export type TradeType = 'BUY' | 'ADD_BUY' | 'SELL' | 'PARTIAL_SELL';

export interface Trade {
  id: string;
  position_id: string;
  trade_type: TradeType;
  trade_date: string;
  price: number;
  quantity: number;
  total_amount: number;
  realized_profit?: number;
  realized_return_pct?: number;
  avg_price_after?: number;
  quantity_after?: number;
  reason?: string;
  notes?: string;
  stock_code?: string;
  stock_name?: string;
  created_at: string;
}

export interface TradeUpdateData {
  price?: number;
  quantity?: number;
  trade_date?: string;
  reason?: string;
  notes?: string;
}

export interface TradeListResponse {
  trades: Trade[];
  total_count: number;
}

export interface TradeSummary {
  total_trades: number;
  buy_count: number;
  sell_count: number;
  total_buy_amount: number;
  total_sell_amount: number;
  total_realized_profit: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  avg_profit_per_trade: number;
  avg_return_pct: number;
}

export interface MonthlyTradeStats {
  month: string;
  trade_count: number;
  buy_count: number;
  sell_count: number;
  realized_profit: number;
  win_rate: number;
}

export interface TickerTradeStats {
  ticker: string;
  stock_name?: string;
  trade_count: number;
  total_buy_amount: number;
  total_sell_amount: number;
  realized_profit: number;
  avg_return_pct: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
}

export interface TradeAnalysisResponse {
  summary: TradeSummary;
  monthly_stats: MonthlyTradeStats[];
  ticker_stats: TickerTradeStats[];
  recent_trades: Trade[];
}
