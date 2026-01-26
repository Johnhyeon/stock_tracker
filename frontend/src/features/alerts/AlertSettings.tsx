import { useEffect, useState, useCallback } from 'react'
import { Card } from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Badge from '../../components/ui/Badge'
import { alertApi } from '../../services/api'
import type {
  AlertRule,
  AlertType,
  NotificationChannel,
  NotificationLog,
  AlertSettings as AlertSettingsType,
} from '../../types/data'

const ALERT_TYPE_LABELS: Record<AlertType, string> = {
  youtube_surge: 'YouTube 급증 감지',
  disclosure_important: '중요 공시 발생',
  fomo_warning: 'FOMO 위험 경고',
  target_reached: '목표가 도달',
  fundamental_deterioration: '펀더멘털 악화',
  time_expired: '예상 기간 초과',
  trader_new_mention: '트레이더 신규 언급',
  trader_cross_check: '트레이더 교차 언급',
  custom: '사용자 정의',
}

const CHANNEL_LABELS: Record<NotificationChannel, string> = {
  telegram: '텔레그램',
  email: '이메일',
  both: '둘 다',
}

export default function AlertSettings() {
  const [settings, setSettings] = useState<AlertSettingsType | null>(null)
  const [rules, setRules] = useState<AlertRule[]>([])
  const [logs, setLogs] = useState<NotificationLog[]>([])
  const [loading, setLoading] = useState(true)
  const [testLoading, setTestLoading] = useState(false)
  const [testResult, setTestResult] = useState<string | null>(null)
  const [showAddRule, setShowAddRule] = useState(false)
  const [newRule, setNewRule] = useState<{
    name: string
    alert_type: AlertType
    channel: NotificationChannel
    cooldown_minutes: number
  }>({
    name: '',
    alert_type: 'youtube_surge',
    channel: 'telegram',
    cooldown_minutes: 60,
  })

  const fetchData = useCallback(async () => {
    try {
      const [settingsData, rulesData, logsData] = await Promise.all([
        alertApi.getSettings(),
        alertApi.listRules(),
        alertApi.listLogs({ limit: 20 }),
      ])
      setSettings(settingsData)
      setRules(rulesData)
      setLogs(logsData)
    } catch (err) {
      console.error('Failed to fetch alert data:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleTestNotification = async (channel: NotificationChannel) => {
    setTestLoading(true)
    setTestResult(null)
    try {
      const result = await alertApi.testNotification({
        channel,
        title: '테스트 알림',
        message: 'Investment Tracker 알림 시스템이 정상적으로 작동합니다.',
      })
      setTestResult(result.success ? '테스트 알림 전송 성공!' : `실패: ${result.error}`)
    } catch (err) {
      setTestResult('알림 전송 중 오류가 발생했습니다.')
    } finally {
      setTestLoading(false)
    }
  }

  const handleToggleRule = async (ruleId: string) => {
    try {
      await alertApi.toggleRule(ruleId)
      fetchData()
    } catch (err) {
      console.error('Failed to toggle rule:', err)
    }
  }

  const handleDeleteRule = async (ruleId: string) => {
    if (!confirm('이 알림 규칙을 삭제하시겠습니까?')) return
    try {
      await alertApi.deleteRule(ruleId)
      fetchData()
    } catch (err) {
      console.error('Failed to delete rule:', err)
    }
  }

  const handleAddRule = async () => {
    if (!newRule.name.trim()) return
    try {
      await alertApi.createRule({
        name: newRule.name,
        alert_type: newRule.alert_type,
        channel: newRule.channel,
        cooldown_minutes: newRule.cooldown_minutes,
        is_enabled: true,
        conditions: {},
      })
      setShowAddRule(false)
      setNewRule({
        name: '',
        alert_type: 'youtube_surge',
        channel: 'telegram',
        cooldown_minutes: 60,
      })
      fetchData()
    } catch (err) {
      console.error('Failed to add rule:', err)
    }
  }

  const handleTriggerCheck = async () => {
    try {
      const result = await alertApi.triggerCheck()
      alert(`알림 체크 완료: ${result.triggered_count}건 발송됨`)
      fetchData()
    } catch (err) {
      alert('알림 체크 중 오류가 발생했습니다.')
    }
  }

  if (loading) {
    return <p className="text-gray-500">로딩 중...</p>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">알림 설정</h1>
        <Button onClick={handleTriggerCheck} variant="secondary">
          알림 체크 실행
        </Button>
      </div>

      {/* 연동 상태 */}
      <Card className="p-4">
        <h2 className="font-semibold mb-4">알림 채널 상태</h2>
        <div className="grid grid-cols-2 gap-4">
          {/* 텔레그램 */}
          <div className="p-4 border rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="font-medium">텔레그램</span>
              <div className={`w-3 h-3 rounded-full ${settings?.telegram_configured ? 'bg-green-500' : 'bg-gray-400'}`} />
            </div>
            {settings?.telegram_configured ? (
              <>
                <p className="text-sm text-gray-600">
                  @{settings.telegram_bot_username || '설정됨'}
                </p>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => handleTestNotification('telegram')}
                  disabled={testLoading}
                  className="mt-2"
                >
                  테스트 발송
                </Button>
              </>
            ) : (
              <p className="text-sm text-gray-500">
                TELEGRAM_BOT_TOKEN과 TELEGRAM_CHAT_ID를 .env에 설정하세요
              </p>
            )}
          </div>

          {/* 이메일 */}
          <div className="p-4 border rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="font-medium">이메일</span>
              <div className={`w-3 h-3 rounded-full ${settings?.email_configured ? 'bg-green-500' : 'bg-gray-400'}`} />
            </div>
            {settings?.email_configured ? (
              <>
                <p className="text-sm text-gray-600">{settings.smtp_host}</p>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => handleTestNotification('email')}
                  disabled={testLoading}
                  className="mt-2"
                >
                  테스트 발송
                </Button>
              </>
            ) : (
              <p className="text-sm text-gray-500">
                SMTP_HOST, SMTP_USER 등을 .env에 설정하세요
              </p>
            )}
          </div>
        </div>

        {testResult && (
          <p className={`mt-4 text-sm ${testResult.includes('성공') ? 'text-green-600' : 'text-red-600'}`}>
            {testResult}
          </p>
        )}
      </Card>

      {/* 알림 규칙 */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold">
            알림 규칙 ({settings?.enabled_rules}/{settings?.total_rules} 활성화)
          </h2>
          <Button onClick={() => setShowAddRule(true)} size="sm">
            규칙 추가
          </Button>
        </div>

        {/* 새 규칙 추가 폼 */}
        {showAddRule && (
          <div className="mb-4 p-4 bg-gray-50 rounded-lg space-y-3">
            <input
              type="text"
              placeholder="규칙 이름"
              value={newRule.name}
              onChange={(e) => setNewRule({ ...newRule, name: e.target.value })}
              className="w-full px-3 py-2 border rounded"
            />
            <div className="grid grid-cols-3 gap-3">
              <select
                value={newRule.alert_type}
                onChange={(e) => setNewRule({ ...newRule, alert_type: e.target.value as AlertType })}
                className="px-3 py-2 border rounded"
              >
                {Object.entries(ALERT_TYPE_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
              <select
                value={newRule.channel}
                onChange={(e) => setNewRule({ ...newRule, channel: e.target.value as NotificationChannel })}
                className="px-3 py-2 border rounded"
              >
                {Object.entries(CHANNEL_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
              <input
                type="number"
                placeholder="쿨다운 (분)"
                value={newRule.cooldown_minutes}
                onChange={(e) => setNewRule({ ...newRule, cooldown_minutes: Number(e.target.value) })}
                className="px-3 py-2 border rounded"
              />
            </div>
            <div className="flex gap-2">
              <Button onClick={handleAddRule} size="sm">추가</Button>
              <Button onClick={() => setShowAddRule(false)} size="sm" variant="secondary">취소</Button>
            </div>
          </div>
        )}

        {/* 규칙 목록 */}
        {rules.length === 0 ? (
          <p className="text-gray-500 text-center py-4">등록된 알림 규칙이 없습니다.</p>
        ) : (
          <div className="space-y-2">
            {rules.map((rule) => (
              <div
                key={rule.id}
                className={`p-3 border rounded-lg flex items-center justify-between ${
                  rule.is_enabled ? 'bg-white' : 'bg-gray-50'
                }`}
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className={`font-medium ${!rule.is_enabled && 'text-gray-400'}`}>
                      {rule.name}
                    </span>
                    <Badge variant={rule.is_enabled ? 'success' : 'default'}>
                      {rule.is_enabled ? '활성' : '비활성'}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2 mt-1 text-sm text-gray-500">
                    <span>{ALERT_TYPE_LABELS[rule.alert_type]}</span>
                    <span>•</span>
                    <span>{CHANNEL_LABELS[rule.channel]}</span>
                    <span>•</span>
                    <span>쿨다운 {rule.cooldown_minutes}분</span>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => handleToggleRule(rule.id)}
                  >
                    {rule.is_enabled ? '비활성화' : '활성화'}
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={() => handleDeleteRule(rule.id)}
                  >
                    삭제
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* 최근 알림 로그 */}
      <Card className="p-4">
        <h2 className="font-semibold mb-4">최근 알림 로그</h2>
        {logs.length === 0 ? (
          <p className="text-gray-500 text-center py-4">알림 로그가 없습니다.</p>
        ) : (
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {logs.map((log) => (
              <div
                key={log.id}
                className={`p-3 border rounded-lg text-sm ${
                  log.is_success ? 'bg-green-50' : 'bg-red-50'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge variant={log.is_success ? 'success' : 'danger'}>
                      {log.is_success ? '성공' : '실패'}
                    </Badge>
                    <span className="font-medium">{log.title}</span>
                  </div>
                  <span className="text-gray-500">
                    {new Date(log.created_at).toLocaleString()}
                  </span>
                </div>
                <p className="text-gray-600 mt-1">{log.message}</p>
                {log.error_message && (
                  <p className="text-red-600 mt-1">{log.error_message}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
