import { useEffect, useState } from 'react'
import { Card } from '../../components/ui/Card'
import { healthApi } from '../../services/api'
import type { AllAPIHealthStatus } from '../../types/data'

export default function APIHealthCheck() {
  const [health, setHealth] = useState<AllAPIHealthStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const checkHealth = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await healthApi.checkAll()
      setHealth(data)
    } catch (err) {
      setError('헬스체크 실패')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    checkHealth()
  }, [])

  const StatusIndicator = ({
    configured,
    connected,
    error,
  }: {
    configured: boolean
    connected: boolean
    error?: string | null
  }) => {
    if (!configured) {
      return (
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-gray-400" />
          <span className="text-sm text-gray-500">미설정</span>
        </div>
      )
    }

    if (connected) {
      return (
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-green-500 animate-pulse" />
          <span className="text-sm text-green-600">연결됨</span>
        </div>
      )
    }

    return (
      <div className="flex items-center gap-2">
        <div className="w-3 h-3 rounded-full bg-red-500" />
        <div>
          <span className="text-sm text-red-600">연결 실패</span>
          {error && <p className="text-xs text-red-400 max-w-xs truncate">{error}</p>}
        </div>
      </div>
    )
  }

  const apis = [
    {
      key: 'kis',
      name: 'KIS (한국투자증권)',
      description: '실시간 주가, OHLCV 조회',
    },
    {
      key: 'dart',
      name: 'DART (전자공시)',
      description: '기업 공시 정보 수집',
    },
    {
      key: 'youtube',
      name: 'YouTube Data API',
      description: '종목 언급 영상 수집',
    },
  ] as const

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">API 연결 상태</h2>
        <button
          onClick={checkHealth}
          disabled={loading}
          className="text-sm text-blue-600 hover:text-blue-800 disabled:opacity-50"
        >
          {loading ? '확인 중...' : '새로고침'}
        </button>
      </div>

      {error ? (
        <p className="text-red-500">{error}</p>
      ) : (
        <div className="space-y-4">
          {apis.map((api) => (
            <div
              key={api.key}
              className="flex items-center justify-between py-2 border-b last:border-b-0"
            >
              <div>
                <p className="font-medium">{api.name}</p>
                <p className="text-xs text-gray-500">{api.description}</p>
              </div>
              {loading ? (
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-gray-300 animate-pulse" />
                  <span className="text-sm text-gray-400">확인 중...</span>
                </div>
              ) : health ? (
                <StatusIndicator {...health[api.key]} />
              ) : null}
            </div>
          ))}
        </div>
      )}

      {health && (
        <div className="mt-4 pt-4 border-t">
          <div className="flex gap-4 text-xs text-gray-500">
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-green-500" />
              <span>연결됨</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-red-500" />
              <span>연결 실패</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-gray-400" />
              <span>미설정</span>
            </div>
          </div>
        </div>
      )}
    </Card>
  )
}
