import { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { recoveryApi } from '../../services/api'
import type { GapRecoveryStock, GapRecoveryResponse } from '../../types/recovery'
import { WatchlistStar } from '../../components/WatchlistStar'

/** 갭 메움 비율 바 */
function GapFillBar({ pct }: { pct: number }) {
  // 0% = 시가 수준, 100% = 전일종가 완전 메움, >100% = 갭 이상 회복
  const clamped = Math.min(Math.max(pct, 0), 150)
  const width = Math.min((clamped / 150) * 100, 100)

  let color = 'bg-red-400'
  if (pct >= 100) color = 'bg-green-500'
  else if (pct >= 70) color = 'bg-emerald-400'
  else if (pct >= 40) color = 'bg-amber-400'

  return (
    <div className="flex items-center gap-2">
      <div className="relative w-24 h-2.5 bg-gray-200 dark:bg-t-border rounded-full overflow-hidden">
        {/* 100% 마커 (전일종가 라인) */}
        <div className="absolute left-[66.7%] top-0 w-px h-full bg-gray-400 dark:bg-gray-500 z-10" />
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${width}%` }} />
      </div>
      <span className={`text-xs font-medium tabular-nums w-12 text-right ${
        pct >= 100 ? 'text-green-600 dark:text-green-400' : pct >= 40 ? 'text-amber-600 dark:text-amber-400' : 'text-red-500'
      }`}>
        {pct.toFixed(0)}%
      </span>
    </div>
  )
}

/** 회복 점수 뱃지 */
function ScoreBadge({ score }: { score: number }) {
  let bg = 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400'
  if (score >= 70) bg = 'bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-400'
  else if (score >= 40) bg = 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400'

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-bold tabular-nums ${bg}`}>
      {score.toFixed(0)}
    </span>
  )
}

/** 미니 가격 바 (당일 레인지 중 현재 위치) */
function PriceRangeBar({ stock }: { stock: GapRecoveryStock }) {
  const { low_price, high_price, current_price, open_price, prev_close } = stock
  const range = high_price - low_price
  if (range <= 0) return null

  const currentPos = ((current_price - low_price) / range) * 100
  const openPos = ((open_price - low_price) / range) * 100
  const prevPos = Math.min(100, Math.max(0, ((prev_close - low_price) / range) * 100))

  return (
    <div className="relative w-full h-3 bg-gray-100 dark:bg-t-border rounded-full mt-1">
      {/* 전일종가 마커 */}
      <div
        className="absolute top-0 w-0.5 h-full bg-blue-400 dark:bg-blue-500 z-10 rounded"
        style={{ left: `${prevPos}%` }}
        title={`전일: ${prev_close.toLocaleString()}`}
      />
      {/* 시가 마커 */}
      <div
        className="absolute top-0 w-0.5 h-full bg-gray-400 z-10 rounded"
        style={{ left: `${openPos}%` }}
        title={`시가: ${open_price.toLocaleString()}`}
      />
      {/* 현재가 */}
      <div
        className={`absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full z-20 border-2 border-white dark:border-t-bg-card shadow ${
          current_price >= prev_close ? 'bg-green-500' : 'bg-red-500'
        }`}
        style={{ left: `calc(${currentPos}% - 5px)` }}
        title={`현재: ${current_price.toLocaleString()}`}
      />
    </div>
  )
}

export default function RecoveryPage() {
  const [data, setData] = useState<GapRecoveryResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [minGap, setMinGap] = useState(0.5)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchData = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true)
    try {
      const result = await recoveryApi.getRealtime(minGap, 50)
      setData(result)
    } catch (err) {
      console.error('갭 회복 데이터 로드 실패:', err)
    } finally {
      setLoading(false)
    }
  }, [minGap])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // 자동 새로고침 (60초)
  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current)
    if (autoRefresh) {
      intervalRef.current = setInterval(() => fetchData(false), 60_000)
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [autoRefresh, fetchData])

  const gapOptions = [
    { value: 0.5, label: '0.5%+' },
    { value: 1.0, label: '1%+' },
    { value: 2.0, label: '2%+' },
    { value: 3.0, label: '3%+' },
  ]

  return (
    <div className="space-y-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-t-text-primary">
            Gap Recovery
          </h1>
          <p className="text-sm text-gray-500 dark:text-t-text-muted mt-0.5">
            갭다운 출발 후 장중 회복 빠른 종목
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* 장 상태 */}
          {data && (
            <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
              data.market_status === 'open'
                ? 'bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-400'
                : 'bg-gray-100 text-gray-500 dark:bg-t-border dark:text-t-text-muted'
            }`}>
              <div className={`w-1.5 h-1.5 rounded-full ${data.market_status === 'open' ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
              {data.market_status === 'open' ? '장중' : '장마감'}
            </div>
          )}
          {/* 자동 새로고침 */}
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`px-2.5 py-1.5 text-xs font-medium rounded-lg transition-colors ${
              autoRefresh
                ? 'bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-400'
                : 'bg-gray-100 text-gray-500 dark:bg-t-border dark:text-t-text-muted'
            }`}
          >
            {autoRefresh ? '자동갱신 ON' : '자동갱신 OFF'}
          </button>
          {/* 수동 새로고침 */}
          <button
            onClick={() => fetchData(true)}
            disabled={loading}
            className="px-3 py-1.5 text-xs font-medium bg-gray-100 dark:bg-t-border text-gray-700 dark:text-t-text-secondary rounded-lg hover:bg-gray-200 dark:hover:bg-t-border/80 disabled:opacity-50 transition-colors"
          >
            {loading ? '로딩...' : '새로고침'}
          </button>
        </div>
      </div>

      {/* 통계 + 필터 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4 text-sm">
          {data && (
            <>
              <span className="text-gray-500 dark:text-t-text-muted">
                스캔 <span className="font-medium text-gray-700 dark:text-t-text-secondary">{data.total_scanned}</span>종목
              </span>
              <span className="text-gray-500 dark:text-t-text-muted">
                갭다운 <span className="font-medium text-red-500">{data.total_gap_down}</span>종목
              </span>
              <span className="text-gray-500 dark:text-t-text-muted">
                표시 <span className="font-medium text-gray-700 dark:text-t-text-secondary">{data.count}</span>종목
              </span>
            </>
          )}
        </div>
        {/* 갭 필터 */}
        <div className="flex bg-gray-100 dark:bg-t-border rounded-lg p-0.5">
          {gapOptions.map(opt => (
            <button
              key={opt.value}
              onClick={() => setMinGap(opt.value)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                minGap === opt.value
                  ? 'bg-white dark:bg-t-bg-card text-gray-900 dark:text-t-text-primary shadow-sm'
                  : 'text-gray-500 dark:text-t-text-muted hover:text-gray-700'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* 테이블 */}
      <div className="bg-white dark:bg-t-bg-card rounded-xl border border-gray-200 dark:border-t-border overflow-hidden">
        {loading && !data ? (
          <div className="flex items-center justify-center py-16">
            <div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full" />
          </div>
        ) : !data || data.stocks.length === 0 ? (
          <div className="text-center py-16 text-gray-500 dark:text-t-text-muted">
            {data?.message ? (
              <>
                <div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full mx-auto mb-3" />
                <p className="text-sm font-medium">{data.message}</p>
              </>
            ) : (
              <>
                <p className="text-sm">갭다운 종목이 없습니다.</p>
                <p className="text-xs mt-1">장중에 갭다운(-{minGap}% 이상)으로 시작한 종목이 있을 때 표시됩니다.</p>
              </>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-gray-50 dark:bg-t-bg text-xs text-gray-500 dark:text-t-text-muted">
                  <th className="px-3 py-2.5 text-left w-8">#</th>
                  <th className="px-3 py-2.5 text-left">종목</th>
                  <th className="px-3 py-2.5 text-right">갭</th>
                  <th className="px-3 py-2.5 text-right">현재가</th>
                  <th className="px-3 py-2.5 text-right">시가대비</th>
                  <th className="px-3 py-2.5 text-left w-40">갭 메움</th>
                  <th className="px-3 py-2.5 text-left w-36">당일 레인지</th>
                  <th className="px-3 py-2.5 text-center w-16">점수</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-t-border">
                {data.stocks.map((stock, idx) => (
                  <tr
                    key={stock.stock_code}
                    className="hover:bg-gray-50 dark:hover:bg-t-border/30 transition-colors"
                  >
                    <td className="px-3 py-2.5 text-sm text-gray-400 dark:text-t-text-muted">{idx + 1}</td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-1">
                        <WatchlistStar stockCode={stock.stock_code} stockName={stock.stock_name} />
                        <Link
                          to={`/stocks/${stock.stock_code}`}
                          className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline"
                        >
                          {stock.stock_name}
                        </Link>
                      </div>
                      {stock.themes.length > 0 && (
                        <div className="flex gap-1 mt-0.5">
                          {stock.themes.slice(0, 2).map(t => (
                            <span key={t} className="text-[10px] px-1.5 py-0.5 bg-gray-100 dark:bg-t-border rounded text-gray-500 dark:text-t-text-muted">
                              {t}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-sm text-right">
                      <span className="text-red-500 font-medium tabular-nums">{stock.gap_pct.toFixed(1)}%</span>
                    </td>
                    <td className="px-3 py-2.5 text-sm text-right tabular-nums">
                      <span className={stock.is_above_prev_close ? 'text-green-600 dark:text-green-400' : 'text-gray-700 dark:text-t-text-secondary'}>
                        {stock.current_price.toLocaleString()}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-sm text-right tabular-nums">
                      <span className={stock.change_from_open_pct >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-500'}>
                        {stock.change_from_open_pct >= 0 ? '+' : ''}{stock.change_from_open_pct.toFixed(1)}%
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <GapFillBar pct={stock.gap_fill_pct} />
                    </td>
                    <td className="px-3 py-2.5">
                      <PriceRangeBar stock={stock} />
                    </td>
                    <td className="px-3 py-2.5 text-center">
                      <ScoreBadge score={stock.recovery_score} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 범례 */}
      <div className="flex items-center gap-6 text-xs text-gray-400 dark:text-t-text-muted px-1">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 bg-blue-400 rounded" />
          <span>전일종가</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 bg-gray-400 rounded" />
          <span>시가</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-green-500" />
          <span>현재가(전일 상회)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-red-500" />
          <span>현재가(전일 하회)</span>
        </div>
        <span className="ml-auto">갭 메움 바의 세로선 = 100% (전일종가 도달)</span>
      </div>
    </div>
  )
}
