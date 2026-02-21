import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'
import { analysisApi } from '../../services/api'
import type { TimelineAnalysis, FomoAnalysis } from '../../types/idea'

export default function Analysis() {
  const [timeline, setTimeline] = useState<TimelineAnalysis | null>(null)
  const [fomo, setFomo] = useState<FomoAnalysis | null>(null)
  const [performance, setPerformance] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'timeline' | 'fomo' | 'performance'>('timeline')

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        const [timelineData, fomoData, perfData] = await Promise.all([
          analysisApi.getTimeline(),
          analysisApi.getFomo(),
          analysisApi.getPerformance(),
        ])
        setTimeline(timelineData)
        setFomo(fomoData)
        setPerformance(perfData)
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  if (loading) return <div className="text-center py-10">로딩 중...</div>

  const tabs = [
    { id: 'timeline', label: '시간차 분석' },
    { id: 'fomo', label: 'FOMO 분석' },
    { id: 'performance', label: '성과 분석' },
  ] as const

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-t-text-primary mb-6">복기 & 분석</h1>

      <div className="border-b border-gray-200 dark:border-t-border mb-6">
        <nav className="flex space-x-8">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === tab.id
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 dark:text-t-text-muted hover:text-gray-700 dark:hover:text-t-text-secondary hover:border-gray-300 dark:hover:border-t-border-hover'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {activeTab === 'timeline' && timeline && (
        <div className="space-y-6">
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardContent>
                <div className="text-sm text-gray-500 dark:text-t-text-muted">평균 시간차</div>
                <div className="text-2xl font-bold">
                  {timeline.avg_time_diff > 0 ? '+' : ''}
                  {timeline.avg_time_diff.toFixed(1)}일
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent>
                <div className="text-sm text-gray-500 dark:text-t-text-muted">조기 청산</div>
                <div className="text-2xl font-bold text-yellow-600">{timeline.early_exits}</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent>
                <div className="text-sm text-gray-500 dark:text-t-text-muted">적정 청산</div>
                <div className="text-2xl font-bold text-green-600">{timeline.on_time_exits}</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent>
                <div className="text-sm text-gray-500 dark:text-t-text-muted">지연 청산</div>
                <div className="text-2xl font-bold text-red-600">{timeline.late_exits}</div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold">청산 이력</h2>
            </CardHeader>
            <CardContent>
              {timeline.entries.length === 0 ? (
                <p className="text-gray-500 dark:text-t-text-muted text-center py-4">청산 이력이 없습니다.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200 dark:divide-t-border">
                    <thead>
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-t-text-muted uppercase">
                          종목
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-t-text-muted uppercase">
                          유형
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-t-text-muted uppercase">
                          보유일
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-t-text-muted uppercase">
                          예상일
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-t-text-muted uppercase">
                          시간차
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-t-text-muted uppercase">
                          수익률
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-t-text-muted uppercase">
                          사유
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 dark:divide-t-border">
                      {timeline.entries.map((entry, idx) => (
                        <tr key={idx}>
                          <td className="px-4 py-3 text-sm font-medium">{entry.ticker}</td>
                          <td className="px-4 py-3 text-sm">
                            <Badge variant={entry.idea_type === 'research' ? 'info' : 'default'}>
                              {entry.idea_type === 'research' ? '리서치' : '차트'}
                            </Badge>
                          </td>
                          <td className="px-4 py-3 text-sm">{entry.days_held}일</td>
                          <td className="px-4 py-3 text-sm">{entry.expected_days}일</td>
                          <td className="px-4 py-3 text-sm">
                            <span
                              className={
                                entry.time_diff_days < -7
                                  ? 'text-yellow-600'
                                  : entry.time_diff_days > 7
                                  ? 'text-red-600'
                                  : 'text-green-600'
                              }
                            >
                              {entry.time_diff_days > 0 ? '+' : ''}
                              {entry.time_diff_days}일
                            </span>
                          </td>
                          <td className="px-4 py-3 text-sm">
                            {entry.return_pct != null ? (
                              <span className={entry.return_pct >= 0 ? 'text-green-600' : 'text-red-600'}>
                                {entry.return_pct >= 0 ? '+' : ''}
                                {entry.return_pct.toFixed(2)}%
                              </span>
                            ) : (
                              '-'
                            )}
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-500 dark:text-t-text-muted">{entry.exit_reason || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === 'fomo' && fomo && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold">FOMO 청산 요약</h2>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-3 mb-6">
                <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg">
                  <div className="text-sm text-yellow-600">총 FOMO 청산</div>
                  <div className="text-2xl font-bold text-yellow-700">{fomo.total_fomo_exits}건</div>
                </div>
                <div className="p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
                  <div className="text-sm text-red-600">평균 놓친 수익</div>
                  <div className="text-2xl font-bold text-red-700">
                    {fomo.avg_missed_return_pct != null
                      ? `${fomo.avg_missed_return_pct.toFixed(2)}%`
                      : '-'}
                  </div>
                </div>
                <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                  <div className="text-sm text-blue-600">총 기회비용</div>
                  <div className="text-2xl font-bold text-blue-700">
                    {fomo.total_missed_opportunity !== null
                      ? `${Number(fomo.total_missed_opportunity).toLocaleString()}원`
                      : '-'}
                  </div>
                </div>
              </div>

              <div className="p-4 bg-gray-50 dark:bg-t-bg-elevated rounded-lg">
                <p className="text-gray-700 dark:text-t-text-secondary">{fomo.summary.message}</p>
                {fomo.summary.recommendation && (
                  <p className="text-primary-600 mt-2 font-medium">{fomo.summary.recommendation}</p>
                )}
              </div>
            </CardContent>
          </Card>

          {fomo.fomo_exits.length > 0 && (
            <Card>
              <CardHeader>
                <h2 className="text-lg font-semibold">FOMO 청산 내역</h2>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {fomo.fomo_exits.map((exit, idx) => (
                    <div key={idx} className="p-4 border border-gray-200 dark:border-t-border rounded-lg">
                      <div className="flex justify-between items-start">
                        <div>
                          <div className="font-medium">{exit.ticker}</div>
                          <div className="text-sm text-gray-500 dark:text-t-text-muted">청산일: {exit.exit_date}</div>
                        </div>
                        <div className="text-right">
                          <div className="text-sm text-gray-500 dark:text-t-text-muted">청산 시 수익률</div>
                          <div
                            className={
                              exit.exit_return_pct >= 0 ? 'text-green-600 font-medium' : 'text-red-600 font-medium'
                            }
                          >
                            {exit.exit_return_pct >= 0 ? '+' : ''}
                            {exit.exit_return_pct.toFixed(2)}%
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {activeTab === 'performance' && performance && (
        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold">리서치 포지션 성과</h2>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-t-text-muted">총 거래 수</span>
                  <span className="font-medium">{(performance.research as { count: number })?.count || 0}건</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-t-text-muted">평균 수익률</span>
                  <span className="font-medium">
                    {(performance.research as { avg_return: number | null })?.avg_return !== null
                      ? `${((performance.research as { avg_return: number }).avg_return).toFixed(2)}%`
                      : '-'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-t-text-muted">승률</span>
                  <span className="font-medium">
                    {(performance.research as { win_rate: number | null })?.win_rate !== null
                      ? `${((performance.research as { win_rate: number }).win_rate * 100).toFixed(1)}%`
                      : '-'}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold">차트 포지션 성과</h2>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-t-text-muted">총 거래 수</span>
                  <span className="font-medium">{(performance.chart as { count: number })?.count || 0}건</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-t-text-muted">평균 수익률</span>
                  <span className="font-medium">
                    {(performance.chart as { avg_return: number | null })?.avg_return !== null
                      ? `${((performance.chart as { avg_return: number }).avg_return).toFixed(2)}%`
                      : '-'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-t-text-muted">승률</span>
                  <span className="font-medium">
                    {(performance.chart as { win_rate: number | null })?.win_rate !== null
                      ? `${((performance.chart as { win_rate: number }).win_rate * 100).toFixed(1)}%`
                      : '-'}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
