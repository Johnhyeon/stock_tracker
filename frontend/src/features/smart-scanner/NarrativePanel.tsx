import { useState, useEffect } from 'react'
import { smartScannerApi } from '../../services/api'
import { useFeatureFlags } from '../../hooks/useFeatureFlags'
import type { NarrativeBriefing } from '../../types/smart_scanner'

interface NarrativePanelProps {
  stockCode: string
}

const strengthColors: Record<string, string> = {
  strong: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400',
  moderate: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
  weak: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
}

const strengthLabels: Record<string, string> = {
  strong: '데이터 강함',
  moderate: '보통',
  weak: '약함',
}

const outlookColors: Record<string, string> = {
  bullish: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  neutral: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
  bearish: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
}

const outlookLabels: Record<string, string> = {
  bullish: '긍정적 \u25B2',
  neutral: '중립 \u2015',
  bearish: '부정적 \u25BC',
}

export default function NarrativePanel({ stockCode }: NarrativePanelProps) {
  const features = useFeatureFlags()
  const [briefing, setBriefing] = useState<NarrativeBriefing | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchBriefing = async (forceRefresh = false) => {
    setLoading(true)
    setError(null)
    try {
      const data = await smartScannerApi.getNarrative(stockCode, forceRefresh)
      setBriefing(data)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '브리핑 로드 실패'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchBriefing()
  }, [stockCode])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-amber-500" />
        <span className="ml-3 text-sm text-gray-500 dark:text-t-text-muted">AI 브리핑 생성 중...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-8">
        <p className="text-sm text-gray-500 dark:text-t-text-muted mb-3">{error}</p>
        <button
          onClick={() => fetchBriefing(true)}
          className="text-sm text-amber-600 dark:text-amber-400 hover:underline"
        >
          다시 시도
        </button>
      </div>
    )
  }

  if (!briefing) {
    return (
      <div className="text-center py-8">
        <p className="text-sm text-gray-500 dark:text-t-text-muted mb-3">내러티브 데이터 없음</p>
        <button
          onClick={() => fetchBriefing(true)}
          className="px-3 py-1.5 text-sm bg-amber-500 text-white rounded-lg hover:bg-amber-600 transition-colors"
        >
          AI 브리핑 생성
        </button>
      </div>
    )
  }

  const strength = briefing.narrative_strength || 'weak'
  const outlook = briefing.market_outlook || 'neutral'

  return (
    <div className="space-y-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-gray-900 dark:text-t-text-primary">내러티브 브리핑</h3>
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${strengthColors[strength]}`}>
            {strengthLabels[strength]}
          </span>
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${outlookColors[outlook]}`}>
            {outlookLabels[outlook]}
          </span>
        </div>
        <button
          onClick={() => fetchBriefing(true)}
          className="text-xs text-gray-400 dark:text-t-text-muted hover:text-gray-600 dark:hover:text-t-text-secondary transition-colors"
          title="새로고침"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      </div>

      {/* 한 줄 요약 */}
      {briefing.one_liner && (
        <div className="p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800/50 rounded-lg">
          <p className="text-sm font-medium text-amber-900 dark:text-amber-300">
            {briefing.one_liner}
          </p>
        </div>
      )}

      {/* 재무 하이라이트 */}
      {briefing.financial_highlight && (
        <div className="p-3 bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-200 dark:border-indigo-800/50 rounded-lg">
          <h4 className="text-xs font-semibold text-indigo-700 dark:text-indigo-400 mb-1">재무 하이라이트</h4>
          <p className="text-sm text-indigo-900 dark:text-indigo-300">
            {briefing.financial_highlight}
          </p>
        </div>
      )}

      {/* 왜 움직이는가 */}
      {briefing.why_moving && (
        <Section title="왜 움직이는가?" content={briefing.why_moving} />
      )}

      {/* 테마/섹터 맥락 */}
      {briefing.theme_context && (
        <Section title="테마/섹터 맥락" content={briefing.theme_context} />
      )}

      {/* 전문가 시각 */}
      {features.expert && briefing.expert_perspective && (
        <Section title="전문가 시각" content={briefing.expert_perspective} />
      )}

      {/* 카탈리스트 & 리스크 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {briefing.catalysts.length > 0 && (
          <div className="p-3 bg-emerald-50 dark:bg-emerald-900/10 rounded-lg">
            <h4 className="text-xs font-semibold text-emerald-700 dark:text-emerald-400 mb-2">카탈리스트</h4>
            <ul className="space-y-1">
              {briefing.catalysts.map((c, i) => (
                <li key={i} className="text-xs text-gray-700 dark:text-t-text-secondary flex items-start gap-1.5">
                  <span className="text-emerald-500 mt-0.5">+</span>
                  {c}
                </li>
              ))}
            </ul>
          </div>
        )}
        {briefing.risk_factors.length > 0 && (
          <div className="p-3 bg-red-50 dark:bg-red-900/10 rounded-lg">
            <h4 className="text-xs font-semibold text-red-700 dark:text-red-400 mb-2">리스크</h4>
            <ul className="space-y-1">
              {briefing.risk_factors.map((r, i) => (
                <li key={i} className="text-xs text-gray-700 dark:text-t-text-secondary flex items-start gap-1.5">
                  <span className="text-red-500 mt-0.5">-</span>
                  {r}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* 생성 시각 */}
      {briefing.generated_at && (
        <p className="text-xs text-gray-400 dark:text-t-text-muted text-right">
          생성: {new Date(briefing.generated_at).toLocaleString('ko-KR')}
        </p>
      )}
    </div>
  )
}

function Section({ title, content }: { title: string; content: string }) {
  return (
    <div>
      <h4 className="text-xs font-semibold text-gray-500 dark:text-t-text-muted uppercase tracking-wide mb-1">
        {title}
      </h4>
      <p className="text-sm text-gray-700 dark:text-t-text-secondary leading-relaxed">
        {content}
      </p>
    </div>
  )
}
