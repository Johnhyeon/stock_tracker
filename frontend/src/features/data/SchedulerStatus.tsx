import { useEffect } from 'react'
import { useDataStore } from '../../store/useDataStore'
import { Card } from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'

export default function SchedulerStatus() {
  const { schedulerStatus, schedulerLoading, fetchSchedulerStatus } = useDataStore()

  useEffect(() => {
    fetchSchedulerStatus()
    // 30초마다 갱신
    const interval = setInterval(fetchSchedulerStatus, 30000)
    return () => clearInterval(interval)
  }, [fetchSchedulerStatus])

  const formatNextRunTime = (isoString?: string) => {
    if (!isoString) return '-'
    const date = new Date(isoString)
    return date.toLocaleString('ko-KR', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const getJobLabel = (jobId: string) => {
    const labels: Record<string, string> = {
      price_update: '가격 업데이트',
      disclosure_collect: '공시 수집',
      youtube_collect: 'YouTube 수집',
    }
    return labels[jobId] || jobId
  }

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">스케줄러 상태</h2>
        {schedulerLoading ? (
          <Badge variant="default">확인 중...</Badge>
        ) : schedulerStatus?.running ? (
          <Badge variant="success">실행 중</Badge>
        ) : (
          <Badge variant="danger">중지됨</Badge>
        )}
      </div>

      {schedulerStatus && schedulerStatus.jobs.length > 0 && (
        <div className="space-y-2">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500">
                <th className="pb-2">작업</th>
                <th className="pb-2">다음 실행</th>
              </tr>
            </thead>
            <tbody>
              {schedulerStatus.jobs.map((job) => (
                <tr key={job.id} className="border-t">
                  <td className="py-2">{getJobLabel(job.id)}</td>
                  <td className="py-2 text-gray-600">
                    {formatNextRunTime(job.next_run_time)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
