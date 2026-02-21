import { Fragment, useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { telegramIdeaApi } from '../../../services/api'
import { Card, CardContent } from '../../../components/ui/Card'
import Select from '../../../components/ui/Select'
import Badge from '../../../components/ui/Badge'
import { WatchlistStar } from '../../../components/WatchlistStar'
import type { StockMentionStats, AuthorStats, TraderRanking } from '../../../types/telegram_idea'

export default function IdeaAnalytics() {
  const navigate = useNavigate()
  const [days, setDays] = useState(30)
  const [stockStats, setStockStats] = useState<StockMentionStats[]>([])
  const [authorStats, setAuthorStats] = useState<AuthorStats[]>([])
  const [traderRanking, setTraderRanking] = useState<TraderRanking[]>([])
  const [expandedTrader, setExpandedTrader] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchData() {
      setLoading(true)
      try {
        const [stockRes, authorRes, rankingRes] = await Promise.all([
          telegramIdeaApi.getStockStats(days),
          telegramIdeaApi.getAuthorStats(days),
          telegramIdeaApi.getTraderRanking(days),
        ])
        setStockStats(stockRes.stocks)
        setAuthorStats(authorRes.authors)
        setTraderRanking(rankingRes.traders || [])
        setExpandedTrader(null)
      } catch (err) {
        console.error('통계 로드 실패:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [days])

  const topStocks = useMemo(() => stockStats.slice(0, 10), [stockStats])

  const recentStocks = useMemo(() => {
    return [...stockStats]
      .sort((a, b) => new Date(b.latest_date).getTime() - new Date(a.latest_date).getTime())
      .slice(0, 10)
  }, [stockStats])

  const newStocks = useMemo(() => {
    const threeDaysAgo = new Date()
    threeDaysAgo.setDate(threeDaysAgo.getDate() - 3)
    return stockStats
      .filter(s => {
        const latestDate = new Date(s.latest_date)
        return latestDate >= threeDaysAgo && s.mention_count <= 2
      })
      .sort((a, b) => new Date(b.latest_date).getTime() - new Date(a.latest_date).getTime())
      .slice(0, 8)
  }, [stockStats])

  const topAuthors = useMemo(() => authorStats.slice(0, 10), [authorStats])

  const maxMentions = useMemo(
    () => Math.max(...topStocks.map((s) => s.mention_count), 1),
    [topStocks]
  )

  const maxAuthorIdeas = useMemo(
    () => Math.max(...topAuthors.map((a) => a.idea_count), 1),
    [topAuthors]
  )

  if (loading) {
    return <div className="text-center py-10 text-gray-500 dark:text-t-text-muted">로딩 중...</div>
  }

  return (
    <div className="space-y-4">
      {/* 상단: 기간 선택 + 요약 통계 (한 줄) */}
      <div className="flex items-center gap-4 flex-wrap">
        <Select
          options={[
            { value: '7', label: '7일' },
            { value: '14', label: '14일' },
            { value: '30', label: '30일' },
            { value: '90', label: '90일' },
          ]}
          value={String(days)}
          onChange={(e) => setDays(Number(e.target.value))}
          className="!w-20 !py-1 !text-xs"
        />
        <div className="flex items-center gap-4 text-sm">
          <span>
            <span className="text-gray-400 dark:text-t-text-muted">종목</span>{' '}
            <span className="font-bold font-mono text-primary-600 dark:text-primary-400">
              {stockStats.length}
            </span>
          </span>
          <span>
            <span className="text-gray-400 dark:text-t-text-muted">언급</span>{' '}
            <span className="font-bold font-mono text-emerald-600 dark:text-emerald-400">
              {stockStats.reduce((sum, s) => sum + s.mention_count, 0)}
            </span>
          </span>
          <span>
            <span className="text-gray-400 dark:text-t-text-muted">발신자</span>{' '}
            <span className="font-bold font-mono text-blue-600 dark:text-blue-400">
              {authorStats.length}
            </span>
          </span>
          <span>
            <span className="text-gray-400 dark:text-t-text-muted">아이디어</span>{' '}
            <span className="font-bold font-mono text-purple-600 dark:text-purple-400">
              {authorStats.reduce((sum, a) => sum + a.idea_count, 0)}
            </span>
          </span>
        </div>
      </div>

      {/* 신규 등장 종목 (칩 스타일, 있을 때만) */}
      {newStocks.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-semibold text-yellow-600 dark:text-yellow-400">NEW</span>
          {newStocks.map((stock) => {
            const daysAgo = Math.floor((Date.now() - new Date(stock.latest_date).getTime()) / (1000 * 60 * 60 * 24))
            return (
              <span key={stock.stock_code} className="inline-flex items-center">
                <WatchlistStar stockCode={stock.stock_code} stockName={stock.stock_name} />
                <button
                  onClick={() => navigate(`/stocks/${stock.stock_code}`)}
                  className="inline-flex items-center gap-1 px-2 py-0.5 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded text-xs hover:bg-yellow-100 dark:hover:bg-yellow-900/40 transition-colors"
                >
                  <span className="font-medium text-gray-900 dark:text-t-text-primary">
                    {stock.stock_name}
                  </span>
                  <span className="text-yellow-600 dark:text-yellow-400">
                    {daysAgo === 0 ? '오늘' : `${daysAgo}d`}
                  </span>
                </button>
              </span>
            )
          })}
        </div>
      )}

      {/* 2x2 그리드: 인기 종목 + 최근 언급 + 발신자 + 발신자별 관심 */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* 인기 종목 Top 10 */}
        <Card>
          <CardContent className="p-3">
            <h3 className="text-xs font-semibold text-gray-700 dark:text-t-text-secondary mb-3">
              인기 종목 Top 10
            </h3>
            {topStocks.length === 0 ? (
              <div className="text-center py-4 text-xs text-gray-400 dark:text-t-text-muted">데이터 없음</div>
            ) : (
              <div className="space-y-1.5">
                {topStocks.map((stock, index) => (
                  <div key={stock.stock_code} className="flex items-center gap-2">
                    <span className="text-[10px] text-gray-400 dark:text-t-text-muted w-4 text-right font-mono">
                      {index + 1}
                    </span>
                    <WatchlistStar stockCode={stock.stock_code} stockName={stock.stock_name} />
                    <button
                      onClick={() => navigate(`/stocks/${stock.stock_code}`)}
                      className="text-xs font-medium text-primary-600 dark:text-primary-400 hover:underline w-20 text-left truncate"
                    >
                      {stock.stock_name}
                    </button>
                    <div className="flex-1 flex items-center gap-1.5">
                      <div
                        className="h-4 bg-primary-500 dark:bg-primary-600 rounded-sm"
                        style={{
                          width: `${(stock.mention_count / maxMentions) * 100}%`,
                          minWidth: '4px',
                        }}
                      />
                      <span className="text-[10px] text-gray-500 dark:text-t-text-muted font-mono">
                        {stock.mention_count}
                      </span>
                    </div>
                    <div className="flex gap-0.5">
                      {stock.sources.includes('my') && (
                        <Badge variant="info" size="sm">내</Badge>
                      )}
                      {stock.sources.includes('others') && (
                        <Badge variant="default" size="sm">타</Badge>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* 최근 언급 종목 */}
        <Card>
          <CardContent className="p-3">
            <h3 className="text-xs font-semibold text-gray-700 dark:text-t-text-secondary mb-3">
              최근 언급 종목
            </h3>
            {recentStocks.length === 0 ? (
              <div className="text-center py-4 text-xs text-gray-400 dark:text-t-text-muted">데이터 없음</div>
            ) : (
              <div className="space-y-1">
                {recentStocks.map((stock) => {
                  const latestDate = new Date(stock.latest_date)
                  const daysAgo = Math.floor((Date.now() - latestDate.getTime()) / (1000 * 60 * 60 * 24))
                  return (
                    <div key={stock.stock_code} className="flex items-center justify-between py-0.5">
                      <div className="flex items-center gap-1">
                        <WatchlistStar stockCode={stock.stock_code} stockName={stock.stock_name} />
                        <button
                          onClick={() => navigate(`/stocks/${stock.stock_code}`)}
                          className="text-xs font-medium text-primary-600 dark:text-primary-400 hover:underline"
                        >
                          {stock.stock_name}
                        </button>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-gray-400 dark:text-t-text-muted font-mono">
                          {stock.mention_count}회
                        </span>
                        <span className={`text-[10px] px-1 py-0.5 rounded ${
                          daysAgo === 0
                            ? 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400'
                            : daysAgo <= 2
                            ? 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-400'
                            : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-500 dark:text-t-text-muted'
                        }`}>
                          {daysAgo === 0 ? '오늘' : `${daysAgo}d`}
                        </span>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* 발신자별 아이디어 수 */}
        <Card>
          <CardContent className="p-3">
            <h3 className="text-xs font-semibold text-gray-700 dark:text-t-text-secondary mb-3">
              발신자 Top 10
            </h3>
            {topAuthors.length === 0 ? (
              <div className="text-center py-4 text-xs text-gray-400 dark:text-t-text-muted">데이터 없음</div>
            ) : (
              <div className="space-y-1.5">
                {topAuthors.map((author, index) => (
                  <div key={author.name} className="flex items-center gap-2">
                    <span className="text-[10px] text-gray-400 dark:text-t-text-muted w-4 text-right font-mono">
                      {index + 1}
                    </span>
                    <span className="text-xs font-medium text-gray-900 dark:text-t-text-primary w-24 truncate">
                      {author.name}
                    </span>
                    <div className="flex-1 flex items-center gap-1.5">
                      <div
                        className="h-4 bg-emerald-500 dark:bg-emerald-600 rounded-sm"
                        style={{
                          width: `${(author.idea_count / maxAuthorIdeas) * 100}%`,
                          minWidth: '4px',
                        }}
                      />
                      <span className="text-[10px] text-gray-500 dark:text-t-text-muted font-mono">
                        {author.idea_count}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* 발신자별 관심 종목 */}
        {topAuthors.length > 0 && (
          <Card>
            <CardContent className="p-3">
              <h3 className="text-xs font-semibold text-gray-700 dark:text-t-text-secondary mb-3">
                발신자별 관심 종목
              </h3>
              <div className="space-y-2">
                {topAuthors.slice(0, 6).map((author) => (
                  <div key={author.name}>
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-xs font-medium text-gray-900 dark:text-t-text-primary truncate">
                        {author.name}
                      </span>
                      <span className="text-[10px] text-gray-400 dark:text-t-text-muted">
                        {new Date(author.latest_idea_date).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {author.top_stocks.slice(0, 5).map((stock) => (
                        <button
                          key={stock.stock_code}
                          onClick={() => navigate(`/stocks/${stock.stock_code}`)}
                          className="text-[10px] bg-gray-100 dark:bg-t-bg-elevated text-primary-600 dark:text-primary-400 px-1.5 py-0.5 rounded hover:bg-gray-200 dark:hover:bg-gray-600"
                        >
                          {stock.stock_name} ({stock.count})
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* 트레이더 성과 랭킹 (풀 와이드) */}
      <Card>
        <CardContent className="p-3">
          <h3 className="text-xs font-semibold text-gray-700 dark:text-t-text-secondary mb-3">
            트레이더 성과 랭킹
          </h3>
          {traderRanking.length === 0 ? (
            <div className="text-center py-6 text-xs text-gray-400 dark:text-t-text-muted">
              분석 가능한 트레이더가 없습니다 (최소 3건 언급 필요)
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-gray-400 dark:text-t-text-muted border-b border-gray-100 dark:border-gray-700">
                    <th className="text-left py-1.5 pr-2 w-8">순위</th>
                    <th className="text-left py-1.5 pr-2">트레이더</th>
                    <th className="text-center py-1.5 px-1">언급</th>
                    <th className="text-center py-1.5 px-1 min-w-[80px]">승률</th>
                    <th className="text-right py-1.5 px-1">평균수익률</th>
                    <th className="text-right py-1.5 px-1">총수익률</th>
                    <th className="text-left py-1.5 px-1 hidden sm:table-cell">베스트픽</th>
                    <th className="text-left py-1.5 px-1 hidden sm:table-cell">워스트픽</th>
                  </tr>
                </thead>
                <tbody>
                  {traderRanking.map((trader) => {
                    const medal = trader.rank === 1 ? '\u{1F947}' : trader.rank === 2 ? '\u{1F948}' : trader.rank === 3 ? '\u{1F949}' : ''
                    const isExpanded = expandedTrader === trader.name
                    return (
                      <Fragment key={trader.name}>
                        <tr
                          onClick={() => setExpandedTrader(isExpanded ? null : trader.name)}
                          className="border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-t-bg-elevated cursor-pointer transition-colors"
                        >
                          <td className="py-1.5 pr-2 font-mono">
                            {medal ? `${medal}` : trader.rank}
                          </td>
                          <td className="py-1.5 pr-2 font-medium text-gray-900 dark:text-t-text-primary truncate max-w-[100px]">
                            {trader.name}
                          </td>
                          <td className="py-1.5 px-1 text-center font-mono">{trader.idea_count}건</td>
                          <td className="py-1.5 px-1">
                            <div className="flex items-center gap-1">
                              <div className="flex-1 h-3 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-emerald-500 dark:bg-emerald-600 rounded-full"
                                  style={{ width: `${Math.min(trader.win_rate, 100)}%` }}
                                />
                              </div>
                              <span className="font-mono text-[10px] w-10 text-right">{trader.win_rate}%</span>
                            </div>
                          </td>
                          <td className={`py-1.5 px-1 text-right font-mono font-medium ${
                            trader.avg_return_pct > 0 ? 'text-red-500 dark:text-red-400' : trader.avg_return_pct < 0 ? 'text-blue-500 dark:text-blue-400' : 'text-gray-500'
                          }`}>
                            {trader.avg_return_pct > 0 ? '+' : ''}{trader.avg_return_pct}%
                          </td>
                          <td className={`py-1.5 px-1 text-right font-mono font-medium ${
                            trader.total_return_pct > 0 ? 'text-red-500 dark:text-red-400' : trader.total_return_pct < 0 ? 'text-blue-500 dark:text-blue-400' : 'text-gray-500'
                          }`}>
                            {trader.total_return_pct > 0 ? '+' : ''}{trader.total_return_pct}%
                          </td>
                          <td className="py-1.5 px-1 hidden sm:table-cell">
                            {trader.best_pick && (
                              <button
                                onClick={(e) => { e.stopPropagation(); navigate(`/stocks/${trader.best_pick!.stock_code}`) }}
                                className="hover:underline"
                              >
                                <span className="text-gray-700 dark:text-t-text-secondary">{trader.best_pick.stock_name}</span>
                                <span className="text-red-500 dark:text-red-400 ml-1">+{trader.best_pick.return_pct}%</span>
                              </button>
                            )}
                          </td>
                          <td className="py-1.5 px-1 hidden sm:table-cell">
                            {trader.worst_pick && (
                              <button
                                onClick={(e) => { e.stopPropagation(); navigate(`/stocks/${trader.worst_pick!.stock_code}`) }}
                                className="hover:underline"
                              >
                                <span className="text-gray-700 dark:text-t-text-secondary">{trader.worst_pick.stock_name}</span>
                                <span className={`ml-1 ${trader.worst_pick.return_pct < 0 ? 'text-blue-500 dark:text-blue-400' : 'text-red-500 dark:text-red-400'}`}>
                                  {trader.worst_pick.return_pct > 0 ? '+' : ''}{trader.worst_pick.return_pct}%
                                </span>
                              </button>
                            )}
                          </td>
                        </tr>
                        {isExpanded && (
                          <tr>
                            <td colSpan={8} className="bg-gray-50 dark:bg-t-bg-elevated px-3 py-2">
                              <div className="text-[10px] text-gray-400 dark:text-t-text-muted mb-1">
                                개별 종목 성과 ({trader.picks.length}건)
                              </div>
                              <div className="flex flex-wrap gap-1.5">
                                {trader.picks.map((pick, idx) => (
                                  <button
                                    key={`${pick.stock_code}-${idx}`}
                                    onClick={() => navigate(`/stocks/${pick.stock_code}`)}
                                    className="inline-flex items-center gap-1 px-2 py-0.5 bg-white dark:bg-t-bg-card border border-gray-200 dark:border-gray-700 rounded text-[11px] hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors"
                                  >
                                    <span className="text-gray-700 dark:text-t-text-secondary">{pick.stock_name}</span>
                                    <span className={`font-mono font-medium ${
                                      pick.return_pct > 0 ? 'text-red-500 dark:text-red-400' : pick.return_pct < 0 ? 'text-blue-500 dark:text-blue-400' : 'text-gray-500'
                                    }`}>
                                      {pick.return_pct > 0 ? '+' : ''}{pick.return_pct}%
                                    </span>
                                    <span className="text-gray-300 dark:text-gray-600">|</span>
                                    <span className="text-gray-400 dark:text-t-text-muted">{pick.mention_date.slice(5)}</span>
                                  </button>
                                ))}
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
