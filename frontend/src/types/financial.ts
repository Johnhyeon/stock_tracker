/** 재무제표 관련 타입 */

export interface FinancialStatementItem {
  sj_div: string // BS/IS/CF
  sj_nm?: string
  account_id: string
  account_nm: string
  account_detail?: string
  thstrm_amount?: number | null
  frmtrm_amount?: number | null
  bfefrmtrm_amount?: number | null
  thstrm_nm?: string
  frmtrm_nm?: string
  bfefrmtrm_nm?: string
  ord?: number
}

export interface FinancialRatios {
  per?: number | null
  pbr?: number | null
  roe?: number | null
  roa?: number | null
  operating_margin?: number | null
  net_margin?: number | null
  debt_ratio?: number | null
  current_ratio?: number | null
  revenue_growth?: number | null
  bsns_year?: string
  reprt_code?: string
}

export interface AnnualFinancialData {
  bsns_year: string
  reprt_code: string
  reprt_name: string
  revenue?: number | null
  operating_income?: number | null
  net_income?: number | null
  total_assets?: number | null
  total_liabilities?: number | null
  total_equity?: number | null
  ratios?: FinancialRatios | null
}

export interface FinancialSummary {
  stock_code: string
  corp_code?: string | null
  annual_data: AnnualFinancialData[]
  quarterly_data: AnnualFinancialData[]
  latest_ratios?: FinancialRatios | null
  has_data: boolean
}

export interface FinancialCollectResponse {
  stock_code: string
  collected_count: number
  years_collected: string[]
  message: string
}
