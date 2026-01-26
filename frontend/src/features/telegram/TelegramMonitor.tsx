import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Input from '../../components/ui/Input'
import Badge from '../../components/ui/Badge'
import Modal from '../../components/ui/Modal'
import { telegramMonitorApi } from '../../services/api'
import type {
  TelegramChannel,
  TelegramKeywordMatch,
  TelegramMonitorStatus,
} from '../../types/telegram'

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
}

export default function TelegramMonitor() {
  const [status, setStatus] = useState<TelegramMonitorStatus | null>(null)
  const [channels, setChannels] = useState<TelegramChannel[]>([])
  const [matches, setMatches] = useState<TelegramKeywordMatch[]>([])
  const [keywords, setKeywords] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // 채널 추가 모달
  const [showAddModal, setShowAddModal] = useState(false)
  const [addForm, setAddForm] = useState({
    mode: 'link' as 'link' | 'username' | 'manual',
    link: '',
    username: '',
    channel_id: '',
    channel_name: '',
  })
  const [addLoading, setAddLoading] = useState(false)

  // 매칭 상세 모달
  const [selectedMatch, setSelectedMatch] = useState<TelegramKeywordMatch | null>(null)

  const fetchData = async () => {
    try {
      setLoading(true)
      setError(null)

      const [statusData, channelsData, matchesData, keywordsData] = await Promise.all([
        telegramMonitorApi.getStatus(),
        telegramMonitorApi.getChannels(),
        telegramMonitorApi.getMatches(7, 20),
        telegramMonitorApi.getKeywords(),
      ])

      setStatus(statusData)
      setChannels(channelsData)
      setMatches(matchesData)
      setKeywords(keywordsData.keywords)
    } catch (err) {
      console.error('데이터 로드 실패:', err)
      setError('데이터를 불러오는데 실패했습니다.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const handleAddChannel = async () => {
    if (addForm.mode === 'link' && !addForm.link.trim()) {
      return
    }
    if (addForm.mode === 'username' && !addForm.username.trim()) {
      return
    }
    if (addForm.mode === 'manual' && (!addForm.channel_id || !addForm.channel_name.trim())) {
      return
    }

    setAddLoading(true)
    try {
      if (addForm.mode === 'link') {
        await telegramMonitorApi.addChannel({
          link: addForm.link.trim(),
        })
      } else if (addForm.mode === 'username') {
        await telegramMonitorApi.addChannel({
          username: addForm.username.startsWith('@') ? addForm.username : `@${addForm.username}`,
        })
      } else {
        await telegramMonitorApi.addChannel({
          channel_id: parseInt(addForm.channel_id),
          channel_name: addForm.channel_name,
        })
      }

      setShowAddModal(false)
      setAddForm({ mode: 'link', link: '', username: '', channel_id: '', channel_name: '' })
      fetchData()
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '채널 추가에 실패했습니다.'
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } }
        alert(axiosErr.response?.data?.detail || message)
      } else {
        alert(message)
      }
    } finally {
      setAddLoading(false)
    }
  }

  const handleDeleteChannel = async (channelId: number) => {
    if (!confirm('이 채널을 삭제하시겠습니까?')) return

    try {
      await telegramMonitorApi.deleteChannel(channelId)
      fetchData()
    } catch (err) {
      console.error('채널 삭제 실패:', err)
      alert('채널 삭제에 실패했습니다.')
    }
  }

  const handleToggleChannel = async (channelId: number) => {
    try {
      await telegramMonitorApi.toggleChannel(channelId)
      fetchData()
    } catch (err) {
      console.error('채널 토글 실패:', err)
    }
  }

  const handleRunMonitor = async () => {
    try {
      const result = await telegramMonitorApi.runMonitor()
      alert(
        `모니터링 완료!\n확인 채널: ${result.checked_channels}개\n매칭: ${result.matches_found}개\n알림 발송: ${result.notifications_sent}개`
      )
      fetchData()
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '모니터링 실행에 실패했습니다.'
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } }
        alert(axiosErr.response?.data?.detail || message)
      } else {
        alert(message)
      }
    }
  }

  if (loading) {
    return (
      <div className="text-center py-10">
        <span className="text-gray-500">로딩 중...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-10">
        <span className="text-red-500">{error}</span>
        <Button onClick={fetchData} className="ml-4">
          다시 시도
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">텔레그램 모니터링</h1>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={handleRunMonitor}>
            수동 실행
          </Button>
          <Button onClick={() => setShowAddModal(true)}>+ 채널 추가</Button>
        </div>
      </div>

      {/* 상태 카드 */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent>
            <div className="text-sm text-gray-500">API 상태</div>
            <div className="text-2xl font-bold">
              {status?.is_configured ? (
                <span className="text-green-600">설정됨</span>
              ) : (
                <span className="text-red-600">미설정</span>
              )}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="text-sm text-gray-500">활성 채널</div>
            <div className="text-2xl font-bold">{status?.enabled_channels || 0}개</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="text-sm text-gray-500">모니터링 키워드</div>
            <div className="text-2xl font-bold">{status?.active_keywords || 0}개</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="text-sm text-gray-500">최근 7일 매칭</div>
            <div className="text-2xl font-bold text-primary-600">{status?.recent_matches || 0}건</div>
          </CardContent>
        </Card>
      </div>

      {!status?.is_configured && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <p className="text-yellow-800">
            <strong>설정 필요:</strong> 텔레그램 API가 설정되지 않았습니다.{' '}
            <code className="bg-yellow-100 px-1 rounded">.env</code> 파일에{' '}
            <code className="bg-yellow-100 px-1 rounded">TELEGRAM_API_ID</code>와{' '}
            <code className="bg-yellow-100 px-1 rounded">TELEGRAM_API_HASH</code>를 설정해주세요.
          </p>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* 채널 목록 */}
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">모니터링 채널</h2>
          </CardHeader>
          <CardContent>
            {channels.length === 0 ? (
              <p className="text-gray-500 text-center py-4">등록된 채널이 없습니다.</p>
            ) : (
              <div className="space-y-3">
                {channels.map((channel) => (
                  <div
                    key={channel.id}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                  >
                    <div className="min-w-0 flex-1 mr-2">
                      <div className="font-medium" style={{ wordBreak: 'break-all', maxWidth: '40ch' }}>
                        {channel.channel_name}
                      </div>
                      <div className="text-sm text-gray-500">
                        {channel.channel_username ? `@${channel.channel_username}` : `ID: ${channel.channel_id}`}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={channel.is_enabled ? 'success' : 'default'}>
                        {channel.is_enabled ? '활성' : '비활성'}
                      </Badge>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleToggleChannel(channel.channel_id)}
                      >
                        {channel.is_enabled ? '끄기' : '켜기'}
                      </Button>
                      <Button
                        size="sm"
                        variant="danger"
                        onClick={() => handleDeleteChannel(channel.channel_id)}
                      >
                        삭제
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* 모니터링 키워드 */}
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">모니터링 키워드 (활성 아이디어 종목)</h2>
          </CardHeader>
          <CardContent>
            {keywords.length === 0 ? (
              <p className="text-gray-500 text-center py-4">모니터링할 키워드가 없습니다.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {keywords.map((keyword) => (
                  <span
                    key={keyword}
                    className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm"
                  >
                    {keyword}
                  </span>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* 최근 매칭 기록 */}
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold">최근 매칭 기록</h2>
        </CardHeader>
        <CardContent>
          {matches.length === 0 ? (
            <p className="text-gray-500 text-center py-4">최근 매칭 기록이 없습니다.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2 px-3">시간</th>
                    <th className="text-left py-2 px-3">채널</th>
                    <th className="text-left py-2 px-3">키워드</th>
                    <th className="text-left py-2 px-3">내용</th>
                    <th className="text-center py-2 px-3">알림</th>
                  </tr>
                </thead>
                <tbody>
                  {matches.map((match) => (
                    <tr
                      key={match.id}
                      className="border-b hover:bg-gray-50 cursor-pointer"
                      onClick={() => setSelectedMatch(match)}
                    >
                      <td className="py-2 px-3 text-gray-500">{formatDate(match.message_date)}</td>
                      <td className="py-2 px-3">{match.channel_name}</td>
                      <td className="py-2 px-3">
                        <span className="px-2 py-0.5 bg-blue-100 text-blue-800 rounded text-xs">
                          {match.matched_keyword}
                        </span>
                      </td>
                      <td className="py-2 px-3 max-w-xs truncate">{match.message_text}</td>
                      <td className="py-2 px-3 text-center">
                        {match.notification_sent ? (
                          <span className="text-green-600">발송됨</span>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 채널 추가 모달 */}
      <Modal isOpen={showAddModal} onClose={() => setShowAddModal(false)} title="채널 추가">
        <div className="space-y-4">
          <div className="flex gap-1">
            <button
              className={`flex-1 py-2 px-2 rounded-lg text-sm ${
                addForm.mode === 'link'
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700'
              }`}
              onClick={() => setAddForm({ ...addForm, mode: 'link' })}
            >
              링크
            </button>
            <button
              className={`flex-1 py-2 px-2 rounded-lg text-sm ${
                addForm.mode === 'username'
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700'
              }`}
              onClick={() => setAddForm({ ...addForm, mode: 'username' })}
            >
              @username
            </button>
            <button
              className={`flex-1 py-2 px-2 rounded-lg text-sm ${
                addForm.mode === 'manual'
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700'
              }`}
              onClick={() => setAddForm({ ...addForm, mode: 'manual' })}
            >
              직접 입력
            </button>
          </div>

          {addForm.mode === 'link' ? (
            <Input
              label="텔레그램 링크"
              placeholder="https://t.me/channel_name"
              value={addForm.link}
              onChange={(e) => setAddForm({ ...addForm, link: e.target.value })}
            />
          ) : addForm.mode === 'username' ? (
            <Input
              label="채널 Username"
              placeholder="@channel_username"
              value={addForm.username}
              onChange={(e) => setAddForm({ ...addForm, username: e.target.value })}
            />
          ) : (
            <>
              <Input
                label="채널 ID"
                type="number"
                placeholder="-1001234567890"
                value={addForm.channel_id}
                onChange={(e) => setAddForm({ ...addForm, channel_id: e.target.value })}
              />
              <Input
                label="채널 이름"
                placeholder="채널 표시 이름"
                value={addForm.channel_name}
                onChange={(e) => setAddForm({ ...addForm, channel_name: e.target.value })}
              />
            </>
          )}

          <div className="flex justify-end gap-2 pt-4">
            <Button variant="ghost" onClick={() => setShowAddModal(false)}>
              취소
            </Button>
            <Button onClick={handleAddChannel} loading={addLoading}>
              추가
            </Button>
          </div>
        </div>
      </Modal>

      {/* 매칭 상세 모달 */}
      <Modal
        isOpen={selectedMatch !== null}
        onClose={() => setSelectedMatch(null)}
        title="매칭 상세"
      >
        {selectedMatch && (
          <div className="space-y-4">
            <div>
              <div className="text-sm text-gray-500">채널</div>
              <div className="font-medium">{selectedMatch.channel_name}</div>
            </div>
            <div>
              <div className="text-sm text-gray-500">시간</div>
              <div>{new Date(selectedMatch.message_date).toLocaleString('ko-KR')}</div>
            </div>
            <div>
              <div className="text-sm text-gray-500">매칭 키워드</div>
              <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded">
                {selectedMatch.matched_keyword}
              </span>
            </div>
            <div>
              <div className="text-sm text-gray-500 mb-1">메시지 내용</div>
              <div className="p-3 bg-gray-50 rounded-lg text-sm whitespace-pre-wrap">
                {selectedMatch.message_text}
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
