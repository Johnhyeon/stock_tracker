import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { themePulseApi } from '../../services/api'
import { Card } from '../../components/ui/Card'
import MomentumCards from './components/MomentumCards'
import ThemeTreemap from './components/ThemeTreemap'
import ThemeTimeline from './components/ThemeTimeline'
import CatalystDistribution from './components/CatalystDistribution'
import type { ThemePulseItem, ThemePulseResponse, TimelineResponse, CatalystDistributionResponse } from '../../types/theme_pulse'

type PeriodType = 3 | 7 | 14

export default function ThemePulsePage() {
  const navigate = useNavigate()
  const [days, setDays] = useState<PeriodType>(7)
  const [pulseData, setPulseData] = useState<ThemePulseResponse | null>(null)
  const [timelineData, setTimelineData] = useState<TimelineResponse | null>(null)
  const [catalystData, setCatalystData] = useState<CatalystDistributionResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchAll()
  }, [days])

  const fetchAll = async () => {
    setLoading(true)
    setError(null)
    try {
      const [pulse, timeline, catalyst] = await Promise.all([
        themePulseApi.getPulse(days, 30),
        themePulseApi.getTimeline(days * 2, 8),
        themePulseApi.getCatalystDistribution(days),
      ])
      setPulseData(pulse)
      setTimelineData(timeline)
      setCatalystData(catalyst)
    } catch (err) {
      console.error('테마 펄스 데이터 로드 실패:', err)
      setError('데이터를 불러오는데 실패했습니다.')
    } finally {
      setLoading(false)
    }
  }

  const items: ThemePulseItem[] = pulseData?.items ?? []

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-t-text-primary">Market Theme Pulse</h1>
          <p className="text-sm text-gray-500 dark:text-t-text-muted mt-1">
            뉴스 기반 시장 테마 시각화 — 어떤 테마가 시장을 주도하는가
          </p>
        </div>
        <div className="flex items-center gap-2">
          {([3, 7, 14] as PeriodType[]).map(p => (
            <button
              key={p}
              onClick={() => setDays(p)}
              className={`px-3 py-1.5 text-sm font-medium rounded transition-colors ${
                days === p
                  ? 'bg-amber-500 text-white'
                  : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted hover:bg-gray-200 dark:hover:bg-t-border'
              }`}
            >
              {p}일
            </button>
          ))}
          <button
            onClick={fetchAll}
            disabled={loading}
            className="px-3 py-1.5 text-sm font-medium rounded bg-gray-100 dark:bg-t-bg-elevated hover:bg-gray-200 dark:hover:bg-t-border disabled:opacity-50 ml-2"
          >
            {loading ? '...' : '새로고침'}
          </button>
        </div>
      </div>

      {error && (
        <Card className="p-4 bg-red-50 dark:bg-red-900/20 border-red-200">
          <p className="text-sm text-red-700">{error}</p>
        </Card>
      )}

      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <Card key={i} className="p-8">
              <div className="animate-pulse">
                <div className="h-4 bg-gray-200 dark:bg-t-border rounded w-1/3 mb-4" />
                <div className="h-40 bg-gray-100 dark:bg-t-bg-elevated rounded" />
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <>
          {/* 모멘텀 카드 */}
          {items.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-gray-600 dark:text-t-text-secondary mb-3 uppercase tracking-wider">
                Top Momentum
              </h2>
              <MomentumCards items={items} />
            </section>
          )}

          {/* Treemap */}
          {items.length > 0 && (
            <Card className="p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-bold text-gray-900 dark:text-t-text-primary">
                  테마 지도
                </h2>
                <div className="text-xs text-gray-400 dark:text-t-text-muted">
                  크기=뉴스 수 | 색상=모멘텀 | 클릭하여 상세 보기
                </div>
              </div>
              <ThemeTreemap items={items} />
            </Card>
          )}

          {/* 타임라인 */}
          <Card className="p-5">
            <h2 className="text-base font-bold text-gray-900 dark:text-t-text-primary mb-4">
              테마 뉴스 추이
            </h2>
            <ThemeTimeline data={timelineData} />
          </Card>

          {/* 재료 분포 */}
          <Card className="p-5">
            <h2 className="text-base font-bold text-gray-900 dark:text-t-text-primary mb-4">
              뉴스 재료 분포
            </h2>
            <CatalystDistribution data={catalystData} />
          </Card>

          {/* 테마 테이블 */}
          {items.length > 0 && (
            <Card compact>
              <div className="px-5 py-3.5 border-b border-gray-200 dark:border-t-border">
                <h2 className="text-base font-bold text-gray-900 dark:text-t-text-primary">
                  전체 테마 ({pulseData?.total_themes ?? 0})
                </h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 dark:bg-t-bg-elevated">
                    <tr>
                      <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">#</th>
                      <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">테마</th>
                      <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">뉴스</th>
                      <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">주요</th>
                      <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">모멘텀</th>
                      <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">셋업</th>
                      <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">대표 종목</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item) => (
                      <tr
                        key={item.theme_name}
                        className="border-t border-gray-100 dark:border-t-border hover:bg-gray-50 dark:hover:bg-t-bg-elevated/50 cursor-pointer"
                        onClick={() => navigate(`/themes/${encodeURIComponent(item.theme_name)}`)}
                      >
                        <td className="py-3 px-4 text-gray-400">{item.rank}</td>
                        <td className="py-3 px-4 font-medium text-gray-900 dark:text-t-text-primary">
                          {item.theme_name}
                        </td>
                        <td className="py-3 px-4 text-right font-medium">{item.news_count}</td>
                        <td className="py-3 px-4 text-right">
                          {item.high_importance_count > 0 ? (
                            <span className="text-orange-500 font-medium">{item.high_importance_count}</span>
                          ) : (
                            <span className="text-gray-300 dark:text-t-text-muted">-</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                            item.momentum >= 50
                              ? 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400'
                              : item.momentum >= 20
                              ? 'bg-orange-100 dark:bg-orange-900/30 text-orange-600 dark:text-orange-400'
                              : item.momentum >= 0
                              ? 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted'
                              : 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400'
                          }`}>
                            {item.momentum > 0 ? '+' : ''}{item.momentum}%
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right">
                          {item.setup_score > 0 ? (
                            <span className="font-medium">{item.setup_score.toFixed(1)}</span>
                          ) : (
                            <span className="text-gray-300 dark:text-t-text-muted">-</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-gray-500 dark:text-t-text-muted text-xs">
                          {item.top_stocks.slice(0, 3).map(s => s.name).join(', ')}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {items.length === 0 && (
                <div className="p-8 text-center text-gray-500 dark:text-t-text-muted">
                  데이터가 없습니다. 뉴스 수집이 필요합니다.
                </div>
              )}
            </Card>
          )}

          {/* 요약 */}
          <Card className="p-3 bg-gray-50 dark:bg-t-bg-elevated">
            <div className="flex flex-wrap gap-4 text-xs text-gray-500 dark:text-t-text-muted">
              <span>전체 {pulseData?.total_themes ?? 0}개 테마 | {pulseData?.total_news ?? 0}건 뉴스</span>
              <span className="ml-auto">{pulseData?.generated_at ? new Date(pulseData.generated_at).toLocaleString('ko-KR') : ''}</span>
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
