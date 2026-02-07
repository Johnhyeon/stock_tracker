import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { telegramIdeaApi } from '../../../services/api'
import { Card, CardContent } from '../../../components/ui/Card'
import Select from '../../../components/ui/Select'
import Badge from '../../../components/ui/Badge'
import type { StockMentionStats, AuthorStats } from '../../../types/telegram_idea'

export default function IdeaAnalytics() {
  const navigate = useNavigate()
  const [days, setDays] = useState(30)
  const [stockStats, setStockStats] = useState<StockMentionStats[]>([])
  const [authorStats, setAuthorStats] = useState<AuthorStats[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchData() {
      setLoading(true)
      try {
        const [stockRes, authorRes] = await Promise.all([
          telegramIdeaApi.getStockStats(days),
          telegramIdeaApi.getAuthorStats(days),
        ])
        setStockStats(stockRes.stocks)
        setAuthorStats(authorRes.authors)
      } catch (err) {
        console.error('통계 로드 실패:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [days])

  // 인기 종목 Top 10 (언급 횟수순)
  const topStocks = useMemo(() => stockStats.slice(0, 10), [stockStats])

  // 최근 언급 종목 Top 10 (최신순, 중복 제거)
  const recentStocks = useMemo(() => {
    return [...stockStats]
      .sort((a, b) => new Date(b.latest_date).getTime() - new Date(a.latest_date).getTime())
      .slice(0, 10)
  }, [stockStats])

  // 신규 등장 종목 (최근 3일 내 첫 언급, 언급 1~2회)
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

  // 발신자 Top 10
  const topAuthors = useMemo(() => authorStats.slice(0, 10), [authorStats])

  // 최대 언급 수 (막대 차트 스케일용)
  const maxMentions = useMemo(
    () => Math.max(...topStocks.map((s) => s.mention_count), 1),
    [topStocks]
  )

  // 발신자별 최대 아이디어 수
  const maxAuthorIdeas = useMemo(
    () => Math.max(...topAuthors.map((a) => a.idea_count), 1),
    [topAuthors]
  )

  if (loading) {
    return <div className="text-center py-10 text-gray-500 dark:text-gray-400">로딩 중...</div>
  }

  return (
    <div className="space-y-6">
      {/* 기간 선택 */}
      <div className="flex items-center gap-4">
        <span className="text-sm text-gray-600 dark:text-gray-400">분석 기간:</span>
        <Select
          options={[
            { value: '7', label: '최근 7일' },
            { value: '14', label: '최근 14일' },
            { value: '30', label: '최근 30일' },
            { value: '90', label: '최근 90일' },
          ]}
          value={String(days)}
          onChange={(e) => setDays(Number(e.target.value))}
        />
      </div>

      {/* 신규 등장 + 최근 언급 종목 */}
      {(newStocks.length > 0 || recentStocks.length > 0) && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* 신규 등장 종목 */}
          {newStocks.length > 0 && (
            <Card className="border-l-4 border-l-yellow-500 dark:border-l-yellow-400">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-4">
                  <span className="text-lg">🆕</span>
                  <h3 className="font-semibold text-gray-900 dark:text-gray-100">
                    신규 등장 종목
                  </h3>
                  <span className="text-xs text-gray-500 dark:text-gray-400">(최근 3일, 1~2회 언급)</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {newStocks.map((stock) => {
                    const daysAgo = Math.floor((Date.now() - new Date(stock.latest_date).getTime()) / (1000 * 60 * 60 * 24))
                    return (
                      <button
                        key={stock.stock_code}
                        onClick={() => navigate(`/stocks/${stock.stock_code}`)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg hover:bg-yellow-100 dark:hover:bg-yellow-900/40 transition-colors"
                      >
                        <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                          {stock.stock_name}
                        </span>
                        <span className="text-xs text-yellow-600 dark:text-yellow-400">
                          {daysAgo === 0 ? '오늘' : `${daysAgo}일전`}
                        </span>
                      </button>
                    )
                  })}
                </div>
              </CardContent>
            </Card>
          )}

          {/* 최근 언급 종목 */}
          <Card className="border-l-4 border-l-green-500 dark:border-l-green-400">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-4">
                <span className="text-lg">🔥</span>
                <h3 className="font-semibold text-gray-900 dark:text-gray-100">
                  최근 언급 종목
                </h3>
                <span className="text-xs text-gray-500 dark:text-gray-400">(최신순)</span>
              </div>
              {recentStocks.length === 0 ? (
                <div className="text-center py-4 text-gray-500 dark:text-gray-400">
                  데이터가 없습니다
                </div>
              ) : (
                <div className="space-y-2">
                  {recentStocks.map((stock) => {
                    const latestDate = new Date(stock.latest_date)
                    const daysAgo = Math.floor((Date.now() - latestDate.getTime()) / (1000 * 60 * 60 * 24))
                    return (
                      <div key={stock.stock_code} className="flex items-center justify-between py-1">
                        <button
                          onClick={() => navigate(`/stocks/${stock.stock_code}`)}
                          className="text-sm font-medium text-primary-600 dark:text-primary-400 hover:underline"
                        >
                          {stock.stock_name}
                        </button>
                        <div className="flex items-center gap-3">
                          <span className="text-xs text-gray-500 dark:text-gray-400">
                            {stock.mention_count}회
                          </span>
                          <span className={`text-xs px-1.5 py-0.5 rounded ${
                            daysAgo === 0
                              ? 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400'
                              : daysAgo <= 2
                              ? 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-400'
                              : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
                          }`}>
                            {daysAgo === 0 ? '오늘' : `${daysAgo}일전`}
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* 인기 종목 차트 */}
        <Card>
          <CardContent className="p-4">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">
              🏆 인기 종목 Top 10
            </h3>
            {topStocks.length === 0 ? (
              <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                데이터가 없습니다
              </div>
            ) : (
              <div className="space-y-3">
                {topStocks.map((stock, index) => (
                  <div key={stock.stock_code} className="flex items-center gap-3">
                    <span className="text-sm text-gray-500 dark:text-gray-400 w-6 text-right">
                      {index + 1}
                    </span>
                    <button
                      onClick={() => navigate(`/stocks/${stock.stock_code}`)}
                      className="text-sm font-medium text-primary-600 dark:text-primary-400 hover:underline w-24 text-left truncate"
                    >
                      {stock.stock_name}
                    </button>
                    <div className="flex-1 flex items-center gap-2">
                      <div
                        className="h-5 bg-primary-500 dark:bg-primary-600 rounded"
                        style={{
                          width: `${(stock.mention_count / maxMentions) * 100}%`,
                          minWidth: '8px',
                        }}
                      />
                      <span className="text-xs text-gray-600 dark:text-gray-400">
                        {stock.mention_count}
                      </span>
                    </div>
                    <div className="flex gap-1">
                      {stock.sources.includes('my') && (
                        <Badge variant="info" size="sm">내</Badge>
                      )}
                      {stock.sources.includes('others') && (
                        <Badge variant="default" size="sm">타인</Badge>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* 발신자별 통계 */}
        <Card>
          <CardContent className="p-4">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">
              발신자별 아이디어 수 Top 10
            </h3>
            {topAuthors.length === 0 ? (
              <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                데이터가 없습니다
              </div>
            ) : (
              <div className="space-y-3">
                {topAuthors.map((author, index) => (
                  <div key={author.name} className="flex items-center gap-3">
                    <span className="text-sm text-gray-500 dark:text-gray-400 w-6 text-right">
                      {index + 1}
                    </span>
                    <span className="text-sm font-medium text-gray-900 dark:text-gray-100 min-w-[100px] truncate">
                      {author.name}
                    </span>
                    <div className="flex-1 flex items-center gap-2">
                      <div
                        className="h-5 bg-green-500 dark:bg-green-600 rounded"
                        style={{
                          width: `${(author.idea_count / maxAuthorIdeas) * 100}%`,
                          minWidth: '8px',
                        }}
                      />
                      <span className="text-xs text-gray-600 dark:text-gray-400">
                        {author.idea_count}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* 요약 통계 */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-3xl font-bold text-primary-600 dark:text-primary-400">
              {stockStats.length}
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">언급된 종목 수</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-3xl font-bold text-green-600 dark:text-green-400">
              {stockStats.reduce((sum, s) => sum + s.mention_count, 0)}
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">총 언급 수</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-3xl font-bold text-blue-600 dark:text-blue-400">
              {authorStats.length}
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">발신자 수</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-3xl font-bold text-purple-600 dark:text-purple-400">
              {authorStats.reduce((sum, a) => sum + a.idea_count, 0)}
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">총 아이디어 수</div>
          </CardContent>
        </Card>
      </div>

      {/* 발신자별 TOP 종목 */}
      {topAuthors.length > 0 && (
        <Card>
          <CardContent className="p-4">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">
              발신자별 관심 종목
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="text-left py-2 px-3 text-gray-600 dark:text-gray-400">발신자</th>
                    <th className="text-left py-2 px-3 text-gray-600 dark:text-gray-400">아이디어 수</th>
                    <th className="text-left py-2 px-3 text-gray-600 dark:text-gray-400">관심 종목</th>
                    <th className="text-left py-2 px-3 text-gray-600 dark:text-gray-400">최근 활동</th>
                  </tr>
                </thead>
                <tbody>
                  {topAuthors.map((author) => (
                    <tr
                      key={author.name}
                      className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
                    >
                      <td className="py-2 px-3 font-medium text-gray-900 dark:text-gray-100">
                        {author.name}
                      </td>
                      <td className="py-2 px-3 text-gray-600 dark:text-gray-400">
                        {author.idea_count}
                      </td>
                      <td className="py-2 px-3">
                        <div className="flex flex-wrap gap-1">
                          {author.top_stocks.slice(0, 5).map((stock) => (
                            <button
                              key={stock.stock_code}
                              onClick={() => navigate(`/stocks/${stock.stock_code}`)}
                              className="text-xs bg-gray-100 dark:bg-gray-700 text-primary-600 dark:text-primary-400 px-2 py-0.5 rounded hover:bg-gray-200 dark:hover:bg-gray-600"
                            >
                              {stock.stock_name} ({stock.count})
                            </button>
                          ))}
                        </div>
                      </td>
                      <td className="py-2 px-3 text-gray-500 dark:text-gray-400 text-xs">
                        {new Date(author.latest_idea_date).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
