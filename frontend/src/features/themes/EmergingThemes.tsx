import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { themeSetupApi } from '../../services/api'
import { useFeatureFlags } from '../../hooks/useFeatureFlags'
import { Card } from '../../components/ui/Card'
import { useDataStore } from '../../store/useDataStore'
import type { ThemeSetup, EmergingThemesResponse } from '../../types/theme_setup'
import { PATTERN_TYPE_LABELS, PATTERN_TYPE_COLORS } from '../../types/theme_setup'

export default function EmergingThemes() {
  const navigate = useNavigate()
  const features = useFeatureFlags()
  const [data, setData] = useState<EmergingThemesResponse | null>(null)
  const [_rankTrend, setRankTrend] = useState<{
    dates: string[]
    themes: Array<{ name: string; data: Array<{ date: string; rank: number; score: number }> }>
  } | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [minScore, setMinScore] = useState(30)

  // 전역 수집 상태
  const {
    themeCalculating,
    themeAnalyzing,
    themeCollectingFlow,
  } = useDataStore()

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const prevStatusRef = useRef({ themeCalculating, themeAnalyzing, themeCollectingFlow })

  // 페이지 로드 시 수집 상태 확인
  useEffect(() => {
    const checkCollectionStatus = async () => {
      try {
        const status = await themeSetupApi.getCollectionStatus()
        useDataStore.setState({
          themeCalculating: status.calculate.is_running,
          themeAnalyzing: status.patterns.is_running,
          themeCollectingFlow: status.investor_flow.is_running,
        })
      } catch (err) {
        console.error('수집 상태 확인 실패:', err)
      }
    }
    checkCollectionStatus()
  }, [])

  // 수집 중일 때 폴링
  useEffect(() => {
    const isAnyRunning = themeCalculating || themeAnalyzing || themeCollectingFlow
    const wasAnyRunning = prevStatusRef.current.themeCalculating ||
                          prevStatusRef.current.themeAnalyzing ||
                          prevStatusRef.current.themeCollectingFlow

    // 수집 완료 시 데이터 새로고침
    if (wasAnyRunning && !isAnyRunning) {
      fetchData()
    }

    // 상태 저장
    prevStatusRef.current = { themeCalculating, themeAnalyzing, themeCollectingFlow }

    // 폴링 관리
    if (isAnyRunning && !pollRef.current) {
      pollRef.current = setInterval(async () => {
        try {
          const status = await themeSetupApi.getCollectionStatus()
          useDataStore.setState({
            themeCalculating: status.calculate.is_running,
            themeAnalyzing: status.patterns.is_running,
            themeCollectingFlow: status.investor_flow.is_running,
          })
        } catch (err) {
          console.error('상태 폴링 실패:', err)
        }
      }, 3000)
    } else if (!isAnyRunning && pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
  }, [themeCalculating, themeAnalyzing, themeCollectingFlow])

  useEffect(() => {
    fetchData()
  }, [minScore])

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [result, trendResult] = await Promise.all([
        themeSetupApi.getEmerging(30, minScore),
        themeSetupApi.getRankTrend(14, 10),
      ])
      setData(result)
      setRankTrend(trendResult)
    } catch (err) {
      setError('테마 셋업 데이터를 불러오는데 실패했습니다.')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleCalculate = async () => {
    if (themeCalculating) {
      alert('점수 재계산이 이미 진행 중입니다.')
      return
    }
    useDataStore.setState({ themeCalculating: true })
    try {
      await themeSetupApi.calculate()
    } catch (err) {
      console.error('셋업 계산 실패:', err)
      alert('셋업 계산 실패')
    } finally {
      useDataStore.setState({ themeCalculating: false })
      await fetchData()
    }
  }

  const handleAnalyzePatterns = async () => {
    if (themeAnalyzing) {
      alert('패턴 분석이 이미 진행 중입니다.')
      return
    }
    useDataStore.setState({ themeAnalyzing: true })
    try {
      const result = await themeSetupApi.analyzePatterns()
      alert(`패턴 분석 완료: ${result.stocks_with_pattern}개 패턴 감지`)
      await fetchData()
    } catch (err) {
      console.error('패턴 분석 실패:', err)
      alert('패턴 분석 실패')
    } finally {
      useDataStore.setState({ themeAnalyzing: false })
    }
  }

  const handleCollectInvestorFlow = async () => {
    if (themeCollectingFlow) {
      alert('수급 수집이 이미 진행 중입니다.')
      return
    }
    useDataStore.setState({ themeCollectingFlow: true })
    try {
      const result = await themeSetupApi.collectInvestorFlow()
      const skipped = (result as any).skipped_stocks || 0
      const msg = skipped > 0
        ? `수급 수집 완료: ${result.collected_count}개 수집, ${skipped}개 이미 수집됨 (건너뜀)`
        : `수급 수집 완료: ${result.collected_count}개 종목`
      alert(msg)
      await fetchData()
    } catch (err) {
      console.error('수급 수집 실패:', err)
      alert('수급 수집 실패')
    } finally {
      useDataStore.setState({ themeCollectingFlow: false })
    }
  }

  const getScoreColor = (score: number): string => {
    if (score >= 70) return 'text-red-500'
    if (score >= 50) return 'text-orange-500'
    if (score >= 35) return 'text-yellow-600'
    return 'text-gray-500 dark:text-t-text-muted'
  }

  const getScoreBg = (score: number): string => {
    if (score >= 70) return 'bg-red-50 dark:bg-red-900/20 border-red-200'
    if (score >= 50) return 'bg-orange-50 dark:bg-orange-900/20 border-orange-200 dark:border-orange-800'
    if (score >= 35) return 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200'
    return 'bg-gray-50 dark:bg-t-bg-elevated border-gray-200 dark:border-t-border'
  }

  const getProgressWidth = (score: number, max: number): string => {
    const pct = Math.min((score / max) * 100, 100)
    return `${pct}%`
  }

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Emerging Themes</h1>
          <p className="text-sm text-gray-500 dark:text-t-text-muted mt-1">
            자리를 만들고 있는 테마 - 뉴스 + 차트 패턴 + 언급 데이터 종합 분석
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <select
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="text-sm border rounded px-2 py-1 bg-white dark:bg-t-bg-elevated dark:border-t-border-hover dark:text-t-text-primary"
          >
            <option value={20}>20점 이상</option>
            <option value={30}>30점 이상</option>
            <option value={40}>40점 이상</option>
            <option value={50}>50점 이상</option>
          </select>
          <button
            onClick={handleCollectInvestorFlow}
            disabled={themeCollectingFlow}
            className="px-3 py-1.5 text-sm bg-cyan-500 text-white rounded hover:bg-cyan-600 disabled:opacity-50"
          >
            {themeCollectingFlow ? '수집 중...' : '수급 수집'}
          </button>
          <button
            onClick={handleAnalyzePatterns}
            disabled={themeAnalyzing}
            className="px-3 py-1.5 text-sm bg-green-500 text-white rounded hover:bg-green-600 disabled:opacity-50"
          >
            {themeAnalyzing ? '분석 중...' : '패턴 분석'}
          </button>
          <button
            onClick={handleCalculate}
            disabled={themeCalculating}
            className="px-3 py-1.5 text-sm bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
          >
            {themeCalculating ? '계산 중...' : '점수 재계산'}
          </button>
        </div>
      </div>

      {/* 에러 */}
      {error && (
        <Card className="p-4 bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800">
          <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
        </Card>
      )}

      {/* 요약 통계 */}
      {data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="p-4 text-center">
            <p className="text-sm text-gray-500 dark:text-t-text-muted">이머징 테마</p>
            <p className="text-2xl font-bold text-blue-600">{data.total_count}개</p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-sm text-gray-500 dark:text-t-text-muted">1위 테마</p>
            <p className="text-lg font-bold text-red-600 truncate">
              {data.themes[0]?.theme_name || '-'}
            </p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-sm text-gray-500 dark:text-t-text-muted">1위 점수</p>
            <p className="text-2xl font-bold">{data.themes[0]?.total_score.toFixed(1) || '-'}</p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-sm text-gray-500 dark:text-t-text-muted">분석 시간</p>
            <p className="text-sm font-medium">
              {new Date(data.generated_at).toLocaleTimeString('ko-KR', {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </p>
          </Card>
        </div>
      )}

      {/* 테마 리스트 */}
      {loading ? (
        <Card className="p-8 text-center">
          <div className="animate-pulse">
            <div className="h-4 bg-gray-200 dark:bg-t-border rounded w-1/3 mx-auto mb-4"></div>
            <div className="h-4 bg-gray-200 dark:bg-t-border rounded w-1/2 mx-auto"></div>
          </div>
        </Card>
      ) : data && data.themes.length > 0 ? (
        <div className="space-y-3">
          {data.themes.map((theme, index) => (
            <ThemeSetupCard
              key={theme.theme_name}
              theme={theme}
              rank={index + 1}
              onDetail={() => navigate(`/emerging/${encodeURIComponent(theme.theme_name)}`)}
              getScoreColor={getScoreColor}
              getScoreBg={getScoreBg}
              getProgressWidth={getProgressWidth}
            />
          ))}
        </div>
      ) : (
        <Card className="p-8 text-center text-gray-500 dark:text-t-text-muted">
          조건에 맞는 이머징 테마가 없습니다.
        </Card>
      )}

      {/* 점수 산정 기준 */}
      <Card className="p-4">
        <h3 className="text-sm font-medium text-gray-600 dark:text-t-text-muted mb-2">셋업 점수 산정 기준 (100점 만점)</h3>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm text-gray-500 dark:text-t-text-muted">
          <div>
            <span className="font-medium text-blue-600">뉴스 (25%)</span>
            <p className="text-xs">7일 뉴스 수 + WoW + 출처</p>
          </div>
          <div>
            <span className="font-medium text-green-600">차트 (30%)</span>
            <p className="text-xs">패턴 감지 비율 + 신뢰도</p>
          </div>
          <div>
            <span className="font-medium text-purple-600">언급 (20%)</span>
            <p className="text-xs">YouTube{features.expert ? ' + 전문가' : ''}</p>
          </div>
          <div>
            <span className="font-medium text-cyan-600">수급 (15%)</span>
            <p className="text-xs">외인/기관 순매수</p>
          </div>
          <div>
            <span className="font-medium text-orange-600">가격 (10%)</span>
            <p className="text-xs">7일 평균 등락률</p>
          </div>
        </div>
      </Card>
    </div>
  )
}

interface ThemeSetupCardProps {
  theme: ThemeSetup
  rank: number
  onDetail: () => void
  getScoreColor: (score: number) => string
  getScoreBg: (score: number) => string
  getProgressWidth: (score: number, max: number) => string
}

function ThemeSetupCard({
  theme,
  rank,
  onDetail,
  getScoreColor,
  getScoreBg,
  getProgressWidth,
}: ThemeSetupCardProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <Card
      className={`p-4 cursor-pointer transition-all hover:shadow-md ${getScoreBg(theme.total_score)}`}
      onClick={() => setExpanded(!expanded)}
    >
      {/* 테마 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-gray-400 font-medium">#{rank}</span>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-lg">{theme.theme_name}</h3>
              {theme.is_emerging === 1 && (
                <span className="px-1.5 py-0.5 text-xs bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400 rounded">
                  Emerging
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-t-text-muted mt-1">
              <span>
                {theme.stocks_with_pattern}/{theme.total_stocks}개 종목 패턴 감지
              </span>
            </div>
          </div>
        </div>
        <div className="text-right">
          <div className={`text-2xl font-bold ${getScoreColor(theme.total_score)}`}>
            {theme.total_score.toFixed(1)}
          </div>
          <div className="text-xs text-gray-400">셋업 점수</div>
        </div>
      </div>

      {/* 점수 breakdown 바 */}
      <div className="mt-4 space-y-2">
        <div className="flex items-center gap-2 text-xs">
          <span className="w-12 text-gray-500 dark:text-t-text-muted">뉴스</span>
          <div className="flex-1 h-2 bg-gray-100 dark:bg-t-bg-elevated rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-400 rounded-full"
              style={{ width: getProgressWidth(theme.news_momentum_score, 25) }}
            />
          </div>
          <span className="w-10 text-right text-gray-600 dark:text-t-text-muted">{theme.news_momentum_score.toFixed(1)}</span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="w-12 text-gray-500 dark:text-t-text-muted">차트</span>
          <div className="flex-1 h-2 bg-gray-100 dark:bg-t-bg-elevated rounded-full overflow-hidden">
            <div
              className="h-full bg-green-400 rounded-full"
              style={{ width: getProgressWidth(theme.chart_pattern_score, 30) }}
            />
          </div>
          <span className="w-10 text-right text-gray-600 dark:text-t-text-muted">{theme.chart_pattern_score.toFixed(1)}</span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="w-12 text-gray-500 dark:text-t-text-muted">언급</span>
          <div className="flex-1 h-2 bg-gray-100 dark:bg-t-bg-elevated rounded-full overflow-hidden">
            <div
              className="h-full bg-purple-400 rounded-full"
              style={{ width: getProgressWidth(theme.mention_score, 20) }}
            />
          </div>
          <span className="w-10 text-right text-gray-600 dark:text-t-text-muted">{theme.mention_score.toFixed(1)}</span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="w-12 text-gray-500 dark:text-t-text-muted">수급</span>
          <div className="flex-1 h-2 bg-gray-100 dark:bg-t-bg-elevated rounded-full overflow-hidden">
            <div
              className="h-full bg-cyan-400 rounded-full"
              style={{ width: getProgressWidth(theme.investor_flow_score || 0, 15) }}
            />
          </div>
          <span className="w-10 text-right text-gray-600 dark:text-t-text-muted">{(theme.investor_flow_score || 0).toFixed(1)}</span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="w-12 text-gray-500 dark:text-t-text-muted">가격</span>
          <div className="flex-1 h-2 bg-gray-100 dark:bg-t-bg-elevated rounded-full overflow-hidden">
            <div
              className="h-full bg-orange-400 rounded-full"
              style={{ width: getProgressWidth(theme.price_action_score, 10) }}
            />
          </div>
          <span className="w-10 text-right text-gray-600 dark:text-t-text-muted">{theme.price_action_score.toFixed(1)}</span>
        </div>
      </div>

      {/* 점수 설명 */}
      {theme.explanation && (
        <div className="mt-3 p-2 bg-white dark:bg-t-bg-card/50 rounded text-xs text-gray-600 dark:text-t-text-muted">
          <span className="text-gray-400 mr-1">요약:</span>
          {theme.explanation}
        </div>
      )}

      {/* 확장 시 상위 종목 */}
      {expanded && theme.top_stocks.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-t-border">
          <h4 className="text-sm font-medium text-gray-600 dark:text-t-text-muted mb-2">패턴 감지 종목</h4>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
            {theme.top_stocks.map((stock) => (
              <div
                key={stock.code}
                className="p-2 bg-white dark:bg-t-bg-card rounded border border-gray-100 dark:border-t-border/50 text-sm"
              >
                <div className="font-medium truncate">{stock.name}</div>
                <div className="text-xs text-gray-500 dark:text-t-text-muted">{stock.code}</div>
                <div className="flex justify-between items-center mt-1">
                  <span
                    className={`text-xs px-1.5 py-0.5 rounded ${
                      PATTERN_TYPE_COLORS[stock.pattern] || 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted'
                    }`}
                  >
                    {PATTERN_TYPE_LABELS[stock.pattern] || stock.pattern}
                  </span>
                  <span className="text-xs text-gray-500 dark:text-t-text-muted">{stock.confidence}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 하단 액션 */}
      <div className="mt-3 flex items-center justify-between">
        <span className="text-xs text-gray-400">
          {expanded ? '접기' : '상세 보기'}
        </span>
        <button
          onClick={(e) => {
            e.stopPropagation()
            onDetail()
          }}
          className="text-xs text-blue-500 hover:underline"
        >
          전체 분석 보기 &rarr;
        </button>
      </div>
    </Card>
  )
}
