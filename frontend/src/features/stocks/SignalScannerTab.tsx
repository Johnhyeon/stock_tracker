import { useState, useEffect, Fragment } from 'react'
import { signalScannerApi, type ScannerSignal, type ChecklistItem, type ScannerAIAdvice } from '../../services/api'
import { Card, CardContent } from '../../components/ui/Card'

const PHASE_COLORS: Record<string, string> = {
  A: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-400 border-purple-300 dark:border-purple-700',
  B: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400 border-blue-300 dark:border-blue-700',
  C: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400 border-amber-300 dark:border-amber-700',
  D: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400 border-green-300 dark:border-green-700',
  unknown: 'bg-gray-100 text-gray-500 dark:bg-gray-700/40 dark:text-gray-400 border-gray-300 dark:border-gray-600',
}

const PHASE_DESC: Record<string, string> = {
  A: '새로운 신고거래량이 터지며 기준봉이 형성되는 초기 단계',
  B: '기준봉 돌파 후 첫 번째 상승 파동이 진행되는 구간',
  C: '눌림목 형성 + 역배열에서 정배열로 전환. 최적 매수 구간',
  D: '정배열 확인 후 전고점 재돌파. 추세 가속 구간',
  unknown: '명확한 ABCD 구간 판별이 어려운 상태',
}

// AI 분석 결과 캐시 (탭 전환/페이지 이동 후 복귀 시에도 유지)
const aiAdviceCache = new Map<string, ScannerAIAdvice>()

export default function SignalScannerTab({ stockCode }: { stockCode: string }) {
  const [signal, setSignal] = useState<ScannerSignal | null>(null)
  const [checklist, setChecklist] = useState<ChecklistItem[]>([])
  const [loading, setLoading] = useState(true)
  const [advice, setAdvice] = useState<ScannerAIAdvice | null>(() => aiAdviceCache.get(stockCode) ?? null)
  const [aiLoading, setAiLoading] = useState(false)
  const [aiError, setAiError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    signalScannerApi.getDetail(stockCode).then(data => {
      if (!cancelled) {
        setSignal(data.signal)
        setChecklist(data.checklist)
        setLoading(false)
      }
    }).catch(() => {
      if (!cancelled) setLoading(false)
    })
    return () => { cancelled = true }
  }, [stockCode])

  const fetchAI = async () => {
    setAiLoading(true)
    setAiError(null)
    try {
      const result = await signalScannerApi.getAIAdvice(stockCode)
      setAdvice(result.advice)
      aiAdviceCache.set(stockCode, result.advice)
    } catch (err: unknown) {
      setAiError(err instanceof Error ? err.message : 'AI 분석 실패')
    } finally {
      setAiLoading(false)
    }
  }

  if (loading) {
    return <div className="text-center py-10 text-gray-500 dark:text-t-text-muted">시그널 분석 로딩 중...</div>
  }

  if (!signal) {
    return <div className="text-center py-10 text-gray-500 dark:text-t-text-muted">시그널 분석 데이터 없음 (OHLCV 60일 이상 필요)</div>
  }

  const phase = signal.abcd_phase
  const totalScore = checklist.reduce((s, c) => s + c.score, 0)
  const maxScore = checklist.reduce((s, c) => s + c.max_score, 0)

  return (
    <div className="space-y-4">
      {/* ABCD Phase Indicator */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-4">
            {/* 현재 구간 뱃지 */}
            <div className={`px-4 py-3 rounded-xl border-2 text-center ${PHASE_COLORS[phase]}`}>
              <div className="text-2xl font-bold">{phase === 'unknown' ? '?' : phase}</div>
              <div className="text-[10px] font-medium mt-0.5">구간</div>
            </div>
            {/* 설명 */}
            <div className="flex-1">
              <div className="text-sm font-semibold text-gray-900 dark:text-t-text-primary mb-1">
                ABCD 매매 구간 분석
              </div>
              <p className="text-xs text-gray-600 dark:text-t-text-muted">{PHASE_DESC[phase]}</p>
              {/* 파이프라인 */}
              <div className="flex items-center gap-1 mt-2">
                {['A', 'B', 'C', 'D'].map((p, i) => {
                  const isActive = p === phase
                  const phases = ['A', 'B', 'C', 'D']
                  const isPast = phases.indexOf(p) < phases.indexOf(phase)
                  return (
                    <Fragment key={p}>
                      <div className={`flex-1 h-2 rounded-full ${
                        isActive ? 'bg-amber-500 dark:bg-amber-400' :
                        isPast ? 'bg-gray-300 dark:bg-gray-500' :
                        'bg-gray-200 dark:bg-gray-700'
                      }`} />
                      {i < 3 && <div className="w-1" />}
                    </Fragment>
                  )
                })}
              </div>
              <div className="flex justify-between text-[10px] text-gray-400 dark:text-t-text-muted mt-0.5 px-1">
                <span>A 기준봉</span>
                <span>B 1차돌파</span>
                <span>C 눌림</span>
                <span>D 재돌파</span>
              </div>
            </div>
            {/* 점수 */}
            <div className="text-right">
              <div className="text-3xl font-bold text-gray-900 dark:text-t-text-primary">
                {signal.total_score.toFixed(0)}
              </div>
              <div className={`text-sm font-bold ${
                signal.grade === 'A' ? 'text-green-600 dark:text-green-400' :
                signal.grade === 'B' ? 'text-blue-600 dark:text-blue-400' :
                signal.grade === 'C' ? 'text-yellow-600 dark:text-yellow-400' :
                'text-gray-500'
              }`}>
                등급 {signal.grade}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 체크리스트 그리드 (2열 x 4행) */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-t-text-primary">매매 체크리스트</h3>
            <span className="text-sm font-bold text-gray-600 dark:text-t-text-muted">
              {totalScore.toFixed(0)} / {maxScore}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {checklist.map(item => (
              <div
                key={item.name}
                className={`p-3 rounded-lg border ${
                  item.passed
                    ? 'bg-green-50 dark:bg-green-900/10 border-green-200 dark:border-green-800/40'
                    : 'bg-gray-50 dark:bg-t-bg border-gray-200 dark:border-t-border'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-sm font-medium ${
                    item.passed ? 'text-green-700 dark:text-green-400' : 'text-gray-600 dark:text-t-text-muted'
                  }`}>
                    {item.passed ? '✓' : '✗'} {item.label}
                  </span>
                  <span className="text-xs text-gray-500 dark:text-t-text-muted">
                    {item.score.toFixed(0)}/{item.max_score}
                  </span>
                </div>
                {/* 점수 바 */}
                <div className="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden mb-1">
                  <div
                    className={`h-full rounded-full ${item.passed ? 'bg-green-500' : 'bg-gray-400'}`}
                    style={{ width: `${(item.score / item.max_score) * 100}%` }}
                  />
                </div>
                <p className="text-xs text-gray-500 dark:text-t-text-muted leading-tight">
                  {item.detail}
                </p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* AI 분석 카드 */}
      <Card>
        <CardContent className="p-4">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-t-text-primary mb-3">AI 시그널 분석</h3>
          {!advice && !aiLoading && (
            <>
              <button
                onClick={fetchAI}
                className="w-full py-2.5 px-4 text-sm font-medium bg-indigo-50 dark:bg-indigo-900/20 text-indigo-700 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-700/40 rounded-lg hover:bg-indigo-100 dark:hover:bg-indigo-900/30 transition-colors"
              >
                AI 분석 요청
              </button>
              {aiError && <p className="text-xs text-red-500 mt-2">{aiError}</p>}
            </>
          )}
          {aiLoading && (
            <div className="text-center py-6 text-sm text-gray-400 dark:text-t-text-muted">
              AI 분석 중... (10~20초 소요)
            </div>
          )}
          {advice && (
            <div className="space-y-3">
              {/* 추천 + 리스크 */}
              <div className="flex items-center gap-3">
                <span className={`px-3 py-1.5 rounded-lg text-sm font-bold ${
                  advice.entry_recommendation === '적극매수' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                  advice.entry_recommendation === '매수대기' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' :
                  advice.entry_recommendation === '매도검토' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' :
                  'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
                }`}>
                  {advice.entry_recommendation}
                </span>
                <span className="text-sm text-gray-600 dark:text-t-text-muted">
                  리스크: <span className="font-medium">{advice.risk_assessment}</span>
                </span>
                <span className="text-sm text-gray-500 dark:text-t-text-muted">
                  신뢰도 {(advice.confidence * 100).toFixed(0)}%
                </span>
              </div>
              {/* 구간 설명 */}
              <p className="text-sm text-gray-700 dark:text-t-text-secondary">{advice.phase_description}</p>
              {/* 핵심 관찰 */}
              {advice.key_observations.length > 0 && (
                <div>
                  <div className="text-xs font-medium text-gray-500 dark:text-t-text-muted mb-1">핵심 관찰</div>
                  <ul className="space-y-1">
                    {advice.key_observations.map((obs, i) => (
                      <li key={i} className="text-sm text-gray-600 dark:text-t-text-muted flex gap-1.5">
                        <span className="text-indigo-500 shrink-0">-</span>
                        <span>{obs}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {/* 진입/청산 */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs font-semibold text-green-600 dark:text-green-400 mb-1">진입 조건</div>
                  {advice.entry_conditions.map((c, i) => (
                    <div key={i} className="text-sm text-gray-600 dark:text-t-text-muted mb-0.5">- {c}</div>
                  ))}
                </div>
                <div>
                  <div className="text-xs font-semibold text-red-600 dark:text-red-400 mb-1">청산 조건</div>
                  {advice.exit_conditions.map((c, i) => (
                    <div key={i} className="text-sm text-gray-600 dark:text-t-text-muted mb-0.5">- {c}</div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
