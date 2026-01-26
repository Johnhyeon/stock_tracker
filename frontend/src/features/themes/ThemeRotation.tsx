import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { themeApi } from '../../services/api'
import { Card } from '../../components/ui/Card'
import type { ThemeRotationResponse, HotTheme } from '../../types/data'

type CategoryType = 'all' | 'tech' | 'bio' | 'energy' | 'defense' | 'finance' | 'consumer' | 'industrial' | 'other'

const CATEGORY_LABELS: Record<CategoryType, string> = {
  all: '전체',
  tech: 'IT/반도체',
  bio: '바이오/제약',
  energy: '에너지/2차전지',
  defense: '방산/우주',
  finance: '금융/부동산',
  consumer: '소비재/유통',
  industrial: '산업재/건설',
  other: '기타',
}

const CATEGORY_COLORS: Record<string, string> = {
  tech: 'bg-blue-500',
  bio: 'bg-green-500',
  energy: 'bg-yellow-500',
  defense: 'bg-red-500',
  finance: 'bg-purple-500',
  consumer: 'bg-pink-500',
  industrial: 'bg-gray-500',
  other: 'bg-slate-500',
}

export default function ThemeRotation() {
  const [data, setData] = useState<ThemeRotationResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [daysBack, setDaysBack] = useState(7)
  const [activeCategory, setActiveCategory] = useState<CategoryType>('all')
  const [expandedTheme, setExpandedTheme] = useState<string | null>(null)

  useEffect(() => {
    fetchData()
  }, [daysBack])

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await themeApi.getRotation(daysBack)
      setData(result)
    } catch (err) {
      setError('테마 데이터를 불러오는데 실패했습니다.')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const formatVolume = (volume: number) => {
    if (volume >= 1_000_000_000) return `${(volume / 1_000_000_000).toFixed(1)}B`
    if (volume >= 1_000_000) return `${(volume / 1_000_000).toFixed(1)}M`
    if (volume >= 1_000) return `${(volume / 1_000).toFixed(1)}K`
    return volume.toString()
  }

  const getFilteredThemes = (): HotTheme[] => {
    if (!data) return []

    if (activeCategory === 'all') {
      return data.hot_themes
    }

    return data.categories[activeCategory] || []
  }

  const getAvailableCategories = (): CategoryType[] => {
    if (!data) return ['all']

    const available: CategoryType[] = ['all']
    Object.keys(data.categories).forEach((cat) => {
      if (data.categories[cat]?.length > 0) {
        available.push(cat as CategoryType)
      }
    })
    return available
  }

  const getScoreColor = (score: number): string => {
    if (score >= 60) return 'text-red-500'
    if (score >= 45) return 'text-orange-500'
    if (score >= 30) return 'text-yellow-600'
    return 'text-gray-500'
  }

  const getScoreBg = (score: number): string => {
    if (score >= 60) return 'bg-red-50 border-red-200'
    if (score >= 45) return 'bg-orange-50 border-orange-200'
    if (score >= 30) return 'bg-yellow-50 border-yellow-200'
    return 'bg-gray-50 border-gray-200'
  }

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Theme Rotation</h1>
          <p className="text-sm text-gray-500 mt-1">
            테마별 순환매 분석 - YouTube & 트레이더 관심종목 기반
          </p>
          <Link
            to="/emerging"
            className="inline-flex items-center gap-1 mt-2 text-sm text-blue-600 hover:underline"
          >
            자리 잡는 테마 보기 (Emerging) &rarr;
          </Link>
        </div>
        <div className="flex gap-2 items-center">
          <select
            value={daysBack}
            onChange={(e) => setDaysBack(Number(e.target.value))}
            className="text-sm border rounded px-2 py-1"
          >
            <option value={3}>최근 3일</option>
            <option value={7}>최근 7일</option>
            <option value={14}>최근 14일</option>
          </select>
          <button
            onClick={fetchData}
            disabled={loading}
            className="px-3 py-1.5 text-sm bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
          >
            {loading ? '분석 중...' : '새로고침'}
          </button>
        </div>
      </div>

      {/* 에러 */}
      {error && (
        <Card className="p-4 bg-red-50 border-red-200">
          <p className="text-sm text-red-700">{error}</p>
        </Card>
      )}

      {/* 요약 통계 */}
      {data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="p-4 text-center">
            <p className="text-sm text-gray-500">감지된 테마</p>
            <p className="text-2xl font-bold text-blue-600">{data.theme_count}개</p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-sm text-gray-500">1위 테마</p>
            <p className="text-lg font-bold text-red-600 truncate">
              {data.summary.top_theme || '-'}
            </p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-sm text-gray-500">평균 점수</p>
            <p className="text-2xl font-bold">{data.summary.avg_theme_score.toFixed(1)}</p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-sm text-gray-500">분석 시간</p>
            <p className="text-sm font-medium">
              {new Date(data.analyzed_at).toLocaleTimeString('ko-KR', {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </p>
          </Card>
        </div>
      )}

      {/* 카테고리 필터 */}
      {data && (
        <div className="flex gap-2 flex-wrap">
          {getAvailableCategories().map((cat) => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`px-3 py-1.5 text-sm rounded-full transition-colors ${
                activeCategory === cat
                  ? `${CATEGORY_COLORS[cat] || 'bg-blue-500'} text-white`
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {CATEGORY_LABELS[cat]}
              {cat !== 'all' && data.categories[cat] && (
                <span className="ml-1 opacity-75">({data.categories[cat].length})</span>
              )}
            </button>
          ))}
        </div>
      )}

      {/* 테마 리스트 */}
      {loading ? (
        <Card className="p-8 text-center">
          <div className="animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-1/3 mx-auto mb-4"></div>
            <div className="h-4 bg-gray-200 rounded w-1/2 mx-auto"></div>
          </div>
        </Card>
      ) : data && getFilteredThemes().length > 0 ? (
        <div className="space-y-3">
          {getFilteredThemes().map((theme, index) => (
            <Card
              key={theme.theme_name}
              className={`p-4 cursor-pointer transition-all hover:shadow-md ${getScoreBg(theme.total_score)}`}
              onClick={() =>
                setExpandedTheme(expandedTheme === theme.theme_name ? null : theme.theme_name)
              }
            >
              {/* 테마 헤더 */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-gray-400 font-medium">#{index + 1}</span>
                  <div>
                    <h3 className="font-semibold text-lg">{theme.theme_name}</h3>
                    <div className="flex items-center gap-2 text-sm text-gray-500 mt-1">
                      <span>{theme.stock_count}개 종목</span>
                      <span>|</span>
                      <span>
                        YouTube {theme.youtube_mentions}회 / 트레이더 {theme.trader_mentions}회
                      </span>
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className={`text-2xl font-bold ${getScoreColor(theme.total_score)}`}>
                    {theme.total_score.toFixed(1)}
                  </div>
                  <div className="text-xs text-gray-400">점수</div>
                </div>
              </div>

              {/* 지표 요약 */}
              <div className="flex gap-4 mt-3 text-sm">
                <div className="flex items-center gap-1">
                  <span className="text-gray-500">평균 등락:</span>
                  <span
                    className={`font-medium ${
                      theme.avg_price_change > 0
                        ? 'text-red-500'
                        : theme.avg_price_change < 0
                        ? 'text-blue-500'
                        : 'text-gray-500'
                    }`}
                  >
                    {theme.avg_price_change > 0 ? '+' : ''}
                    {theme.avg_price_change.toFixed(2)}%
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-gray-500">총 거래량:</span>
                  <span className="font-medium">{formatVolume(theme.total_volume)}</span>
                </div>
              </div>

              {/* 확장된 종목 목록 */}
              {expandedTheme === theme.theme_name && theme.stocks.length > 0 && (
                <div className="mt-4 pt-4 border-t border-gray-200">
                  <h4 className="text-sm font-medium text-gray-600 mb-2">관심 종목</h4>
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
                    {theme.stocks.map((stock) => (
                      <div
                        key={stock.code}
                        className="p-2 bg-white rounded border border-gray-100 text-sm"
                      >
                        <div className="font-medium truncate">{stock.name || stock.code}</div>
                        <div className="text-xs text-gray-500">{stock.code}</div>
                        <div className="flex justify-between items-center mt-1 text-xs">
                          <span className="text-gray-400">
                            {stock.source === 'both' ? 'Y+T' : stock.source === 'youtube' ? 'Y' : 'T'}
                          </span>
                          {stock.price_change !== null && (
                            <span
                              className={
                                stock.price_change > 0
                                  ? 'text-red-500'
                                  : stock.price_change < 0
                                  ? 'text-blue-500'
                                  : 'text-gray-500'
                              }
                            >
                              {stock.price_change > 0 ? '+' : ''}
                              {stock.price_change.toFixed(1)}%
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 확장 표시 */}
              <div className="mt-2 text-center">
                <span className="text-xs text-gray-400">
                  {expandedTheme === theme.theme_name ? '접기' : '상세 보기'}
                </span>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <Card className="p-8 text-center text-gray-500">
          {activeCategory === 'all'
            ? '감지된 테마가 없습니다.'
            : `${CATEGORY_LABELS[activeCategory]} 카테고리에 테마가 없습니다.`}
        </Card>
      )}

      {/* 범례 */}
      <Card className="p-4">
        <h3 className="text-sm font-medium text-gray-600 mb-2">점수 산정 기준</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm text-gray-500">
          <div>
            <span className="font-medium">언급 (40%)</span>
            <p className="text-xs">YouTube + 트레이더 언급</p>
          </div>
          <div>
            <span className="font-medium">종목 수 (20%)</span>
            <p className="text-xs">테마 내 관심 종목</p>
          </div>
          <div>
            <span className="font-medium">주가 상승률 (25%)</span>
            <p className="text-xs">평균 등락률</p>
          </div>
          <div>
            <span className="font-medium">거래량 (15%)</span>
            <p className="text-xs">총 거래대금</p>
          </div>
        </div>
      </Card>
    </div>
  )
}
