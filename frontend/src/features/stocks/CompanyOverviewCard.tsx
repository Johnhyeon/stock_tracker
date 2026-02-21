import { useState, useEffect, useRef, useCallback } from 'react'
import { companyProfileApi, type CompanyProfileData } from '../../services/api'

const RETRY_DELAY = 15 // 자동 재시도 대기 초

export default function CompanyOverviewCard({ stockCode }: { stockCode: string }) {
  const [profile, setProfile] = useState<CompanyProfileData | null>(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')
  const [countdown, setCountdown] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const retryCountRef = useRef(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    companyProfileApi.getProfile(stockCode).then(data => {
      if (!cancelled) {
        setProfile(data)
        setLoading(false)
      }
    }).catch(() => {
      if (!cancelled) setLoading(false)
    })
    return () => { cancelled = true }
  }, [stockCode])

  // 카운트다운 타이머 정리
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [])

  const handleGenerate = useCallback(async (force = false) => {
    setGenerating(true)
    setError('')
    setCountdown(0)
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }

    try {
      const data = await companyProfileApi.generateProfile(stockCode, force)
      if (data?.business_summary) {
        setProfile(data)
        retryCountRef.current = 0
      } else {
        retryCountRef.current += 1
        if (retryCountRef.current < 3) {
          setError(`AI 서버가 바쁩니다. ${RETRY_DELAY}초 후 자동 재시도합니다... (${retryCountRef.current}/3)`)
          startCountdown(force)
        } else {
          setError('여러 번 시도했으나 실패했습니다. 잠시 후 다시 시도해주세요.')
          retryCountRef.current = 0
        }
      }
    } catch (err) {
      console.error('프로필 생성 실패:', err)
      retryCountRef.current += 1
      if (retryCountRef.current < 3) {
        setError(`AI 서버가 바쁩니다. ${RETRY_DELAY}초 후 자동 재시도합니다... (${retryCountRef.current}/3)`)
        startCountdown(force)
      } else {
        setError('여러 번 시도했으나 실패했습니다. 잠시 후 다시 시도해주세요.')
        retryCountRef.current = 0
      }
    } finally {
      setGenerating(false)
    }
  }, [stockCode])

  const startCountdown = useCallback((force: boolean) => {
    setCountdown(RETRY_DELAY)
    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          if (timerRef.current) clearInterval(timerRef.current)
          timerRef.current = null
          handleGenerate(force)
          return 0
        }
        return prev - 1
      })
    }, 1000)
  }, [handleGenerate])

  const cancelRetry = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    setCountdown(0)
    setError('')
    retryCountRef.current = 0
  }

  if (loading) {
    return (
      <div className="bg-white dark:bg-t-bg-card rounded-xl border border-gray-200 dark:border-t-border p-4">
        <div className="animate-pulse flex gap-3">
          <div className="h-4 w-20 bg-gray-200 dark:bg-t-bg-elevated rounded" />
          <div className="h-4 w-48 bg-gray-200 dark:bg-t-bg-elevated rounded" />
        </div>
      </div>
    )
  }

  const hasSummary = profile?.business_summary

  if (!hasSummary) {
    return (
      <div className="bg-white dark:bg-t-bg-card rounded-xl border border-gray-200 dark:border-t-border p-4">
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-500 dark:text-t-text-muted">
            기업 프로필이 아직 생성되지 않았습니다
          </span>
          <button
            onClick={() => handleGenerate()}
            disabled={generating || countdown > 0}
            className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {generating ? '생성 중...' : countdown > 0 ? `재시도 ${countdown}초` : '프로필 생성'}
          </button>
        </div>
        {error && (
          <div className="mt-2 flex items-center gap-2">
            <p className="text-xs text-amber-600 dark:text-amber-400">{error}</p>
            {countdown > 0 && (
              <button
                onClick={cancelRetry}
                className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-t-text-secondary underline flex-shrink-0"
              >
                취소
              </button>
            )}
          </div>
        )}
      </div>
    )
  }

  const products = profile.main_products?.split(',').map(p => p.trim()).filter(Boolean) || []

  return (
    <div className="bg-white dark:bg-t-bg-card rounded-xl border border-gray-200 dark:border-t-border p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          {/* 섹터 + CEO */}
          <div className="flex items-center gap-2 mb-2">
            {profile.sector && (
              <span className="inline-block px-2 py-0.5 text-xs font-medium rounded-full bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400">
                {profile.sector}
              </span>
            )}
            {profile.ceo_name && (
              <span className="text-xs text-gray-500 dark:text-t-text-muted">
                CEO: {profile.ceo_name}
              </span>
            )}
          </div>

          {/* 비즈니스 요약 */}
          <p className="text-sm text-gray-700 dark:text-t-text-secondary leading-relaxed">
            {profile.business_summary}
          </p>

          {/* 주요 제품 태그 */}
          {products.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {products.map(p => (
                <span
                  key={p}
                  className="inline-block px-2 py-0.5 text-xs rounded bg-gray-100 text-gray-600 dark:bg-t-bg-elevated dark:text-t-text-muted"
                >
                  {p}
                </span>
              ))}
            </div>
          )}

          {/* 출처 + 보고서 링크 */}
          {profile.report_source && (
            <div className="flex items-center gap-2 mt-2 text-xs text-gray-400 dark:text-t-text-muted">
              <span>출처: {profile.report_source}</span>
              {profile.report_url && (
                <a
                  href={profile.report_url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="text-indigo-500 hover:text-indigo-600 dark:text-indigo-400 dark:hover:text-indigo-300 cursor-pointer"
                >
                  보고서 원문 &rarr;
                </a>
              )}
            </div>
          )}
        </div>

        {/* 갱신 버튼 */}
        <button
          onClick={() => handleGenerate(true)}
          disabled={generating || countdown > 0}
          className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-t-text-secondary disabled:opacity-50 flex-shrink-0"
          title="프로필 갱신"
        >
          {generating ? '...' : countdown > 0 ? `${countdown}초` : '갱신'}
        </button>
      </div>
      {error && (
        <div className="mt-2 flex items-center gap-2">
          <p className="text-xs text-amber-600 dark:text-amber-400">{error}</p>
          {countdown > 0 && (
            <button
              onClick={cancelRetry}
              className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-t-text-secondary underline flex-shrink-0"
            >
              취소
            </button>
          )}
        </div>
      )}
    </div>
  )
}
