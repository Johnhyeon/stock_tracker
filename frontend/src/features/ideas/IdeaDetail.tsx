import { useEffect, useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useIdeaStore } from '../../store/useIdeaStore'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Badge from '../../components/ui/Badge'
import MarkdownViewer from '../../components/ui/MarkdownViewer'
import { IdeaStockChart } from '../../components/IdeaStockChart'
import { StockFlowPanel } from '../../components/StockFlowPanel'
import { ideaApi, positionApi } from '../../services/api'
import { IdeaDetailSkeleton } from '../../components/SkeletonLoader'
import AddPositionModal from './modals/AddPositionModal'
import ExitPositionModal from './modals/ExitPositionModal'
import AddBuyModal from './modals/AddBuyModal'
import PartialExitModal from './modals/PartialExitModal'
import EditIdeaModal from './modals/EditIdeaModal'
import ExitCheckModal from './modals/ExitCheckModal'
import type { PositionCreate, PositionExit, PositionAddBuy, PositionPartialExit, ExitCheckResult, FundamentalHealth, IdeaUpdate } from '../../types/idea'

// 종목코드 파싱 유틸리티
const extractStockCode = (ticker: string): string | null => {
  const match = ticker.match(/\(([A-Za-z0-9]{6})\)/)
  return match ? match[1] : null
}

const extractStockName = (ticker: string): string => {
  const match = ticker.match(/^(.+)\([A-Za-z0-9]{6}\)$/)
  return match ? match[1] : ticker
}

const formatDate = (dateString: string): string => {
  const date = new Date(dateString)
  return `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, '0')}.${String(date.getDate()).padStart(2, '0')}`
}

export default function IdeaDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { currentIdea, loading, error, fetchIdea } = useIdeaStore()

  const [showAddPosition, setShowAddPosition] = useState(false)
  const [showExitPosition, setShowExitPosition] = useState<string | null>(null)
  const [showAddBuy, setShowAddBuy] = useState<string | null>(null)
  const [showPartialExit, setShowPartialExit] = useState<string | null>(null)
  const [showExitCheck, setShowExitCheck] = useState(false)
  const [showEditIdea, setShowEditIdea] = useState(false)
  const [exitCheckResult, setExitCheckResult] = useState<ExitCheckResult | null>(null)

  useEffect(() => {
    if (id) fetchIdea(id)
  }, [id, fetchIdea])

  const handleAddPosition = async (form: PositionCreate) => {
    if (!id) return
    await ideaApi.createPosition(id, form)
    fetchIdea(id)
    setShowAddPosition(false)
  }

  const handleExitPosition = async (form: PositionExit) => {
    if (!showExitPosition || !id) return
    await positionApi.exit(showExitPosition, form)
    fetchIdea(id)
    setShowExitPosition(null)
  }

  const handleAddBuy = async (form: PositionAddBuy) => {
    if (!showAddBuy || !id) return
    await positionApi.addBuy(showAddBuy, form)
    fetchIdea(id)
    setShowAddBuy(null)
  }

  const handlePartialExit = async (form: PositionPartialExit) => {
    if (!showPartialExit || !id) return
    await positionApi.partialExit(showPartialExit, form)
    fetchIdea(id)
    setShowPartialExit(null)
  }

  const handleCheckExit = async () => {
    if (!id) return
    try {
      const result = await ideaApi.checkExit(id)
      setExitCheckResult(result)
      setShowExitCheck(true)
    } catch (err) {
      console.error(err)
    }
  }

  const handleUpdateHealth = async (health: FundamentalHealth) => {
    if (!id) return
    try {
      await ideaApi.update(id, { fundamental_health: health })
      fetchIdea(id)
    } catch (err) {
      console.error(err)
    }
  }

  const handleDelete = async () => {
    if (!id || !confirm('정말 삭제하시겠습니까?')) return
    try {
      await ideaApi.delete(id)
      navigate('/ideas')
    } catch (err) {
      console.error(err)
    }
  }

  const handleEditIdea = async (form: IdeaUpdate) => {
    if (!id) return
    await ideaApi.update(id, form)
    fetchIdea(id)
    setShowEditIdea(false)
  }

  // FOMO 방지 타이머: 등록 후 24시간 냉각기간 (훅은 early return 전에 호출)
  const COOLDOWN_HOURS = 24
  const fomoTimer = useMemo(() => {
    if (!currentIdea) return null
    if (currentIdea.status !== 'watching' || currentIdea.positions.length > 0) return null
    const createdAt = new Date(currentIdea.created_at).getTime()
    const cooldownEnd = createdAt + COOLDOWN_HOURS * 60 * 60 * 1000
    const now = Date.now()
    const remaining = cooldownEnd - now
    if (remaining <= 0) return null // 냉각 완료
    const hours = Math.floor(remaining / (1000 * 60 * 60))
    const minutes = Math.floor((remaining % (1000 * 60 * 60)) / (1000 * 60))
    return { hours, minutes, remaining }
  }, [currentIdea])

  if (loading) return <IdeaDetailSkeleton />
  if (error) return <div className="text-center py-10 text-red-600">{error}</div>
  if (!currentIdea) return <div className="text-center py-10">아이디어를 찾을 수 없습니다.</div>

  const activeAddBuyPosition = showAddBuy ? currentIdea.positions.find(p => p.id === showAddBuy) ?? null : null
  const activePartialExitPosition = showPartialExit ? currentIdea.positions.find(p => p.id === showPartialExit) ?? null : null

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex justify-between items-start mb-6">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <Badge variant={currentIdea.type === 'research' ? 'info' : 'default'} size="md">
              {currentIdea.type === 'research' ? '리서치' : '차트'}
            </Badge>
            <Badge
              variant={
                currentIdea.status === 'active'
                  ? 'success'
                  : currentIdea.status === 'watching'
                  ? 'warning'
                  : 'default'
              }
              size="md"
            >
              {currentIdea.status === 'active' ? '활성' : currentIdea.status === 'watching' ? '관찰' : '청산'}
            </Badge>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-t-text-primary">
            {currentIdea.tickers.join(', ') || '종목 미지정'}
          </h1>
          {currentIdea.sector && <p className="text-gray-500 dark:text-t-text-muted">{currentIdea.sector}</p>}
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setShowEditIdea(true)}>
            수정
          </Button>
          <Button variant="secondary" onClick={handleCheckExit}>
            청산 체크
          </Button>
          <Button variant="danger" onClick={handleDelete}>
            삭제
          </Button>
        </div>
      </div>

      {/* FOMO 방지 타이머 */}
      {fomoTimer && (
        <div className="mb-6 p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
          <div className="flex items-center gap-3">
            <span className="text-2xl">&#x23F3;</span>
            <div>
              <div className="font-medium text-amber-800 dark:text-amber-200">
                냉각 기간 진행 중
              </div>
              <div className="text-sm text-amber-600 dark:text-amber-400">
                아이디어 등록 후 {COOLDOWN_HOURS}시간 냉각 기간입니다. 충동적 매수를 방지하세요.
              </div>
            </div>
            <div className="ml-auto text-right">
              <div className="text-2xl font-bold text-amber-700 dark:text-amber-300 tabular-nums">
                {fomoTimer.hours}시간 {fomoTimer.minutes}분
              </div>
              <div className="text-xs text-amber-500">남음</div>
            </div>
          </div>
          <div className="mt-2 bg-amber-200 dark:bg-amber-800 rounded-full h-2 overflow-hidden">
            <div
              className="bg-amber-500 h-full rounded-full transition-all"
              style={{ width: `${Math.max(0, 100 - (fomoTimer.remaining / (COOLDOWN_HOURS * 60 * 60 * 1000)) * 100)}%` }}
            />
          </div>
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-3 mb-6">
        <Card>
          <CardContent>
            <div className="text-sm text-gray-500 dark:text-t-text-muted">목표 수익률</div>
            <div className="text-2xl font-bold text-primary-600">
              {Number(currentIdea.target_return_pct)}%
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="text-sm text-gray-500 dark:text-t-text-muted">예상 기간</div>
            <div className="text-2xl font-bold">{currentIdea.expected_timeframe_days}일</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="text-sm text-gray-500 dark:text-t-text-muted">투자 금액</div>
            <div className="text-2xl font-bold">
              {currentIdea.total_invested?.toLocaleString() || 0}원
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="mb-6 flex items-center gap-3">
        <span className="text-sm text-gray-600 dark:text-t-text-muted">펀더멘탈:</span>
        <div className="flex gap-1">
          {[
            { value: 'healthy', label: '건강', color: 'bg-green-500' },
            { value: 'deteriorating', label: '악화', color: 'bg-yellow-500' },
            { value: 'broken', label: '손상', color: 'bg-red-500' },
          ].map((item) => (
            <button
              key={item.value}
              onClick={() => handleUpdateHealth(item.value as FundamentalHealth)}
              className={`px-3 py-1 text-xs rounded-full transition-all ${
                currentIdea.fundamental_health === item.value
                  ? `${item.color} text-white`
                  : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted hover:bg-gray-200 dark:hover:bg-t-border dark:bg-t-border'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <Card className="mb-6">
        <CardHeader>
          <h2 className="text-lg font-semibold">투자 논리</h2>
        </CardHeader>
        <CardContent>
          <MarkdownViewer content={currentIdea.thesis} />
        </CardContent>
      </Card>

      {/* 주가 추이 차트 */}
      {currentIdea.tickers.some((ticker) => extractStockCode(ticker)) && (
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">주가 추이</h2>
              <span className="text-sm text-gray-500 dark:text-t-text-muted">
                {currentIdea.status === 'watching' ? '관심 등록일' : '아이디어 생성일'}({formatDate(currentIdea.created_at)}) 이후
              </span>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              {currentIdea.tickers.map((ticker) => {
                const code = extractStockCode(ticker)
                const name = extractStockName(ticker)
                const initialPrice = currentIdea.metadata?.initial_prices?.[code || '']

                const stockPositions = currentIdea.positions.filter(
                  (p) => p.ticker === code || p.ticker.includes(code || '')
                )

                let avgEntryPrice: number | undefined
                if (stockPositions.length > 0) {
                  const totalQty = stockPositions.reduce((sum, p) => sum + p.quantity, 0)
                  const totalValue = stockPositions.reduce(
                    (sum, p) => sum + Number(p.entry_price) * p.quantity,
                    0
                  )
                  avgEntryPrice = totalQty > 0 ? totalValue / totalQty : undefined
                }

                const entryMarkers = stockPositions
                  .filter((p) => p.entry_date)
                  .map((p) => ({
                    date: p.entry_date as string,
                    price: Number(p.entry_price),
                    quantity: p.quantity,
                  }))

                return code ? (
                  <div key={code} className="grid gap-4 md:grid-cols-3">
                    <div className="md:col-span-2">
                      <IdeaStockChart
                        stockCode={code}
                        stockName={name}
                        initialPrice={initialPrice?.price}
                        avgEntryPrice={avgEntryPrice}
                        entryMarkers={entryMarkers.length > 0 ? entryMarkers : undefined}
                        createdAt={currentIdea.created_at}
                        height={280}
                      />
                    </div>
                    <div>
                      <StockFlowPanel stockCode={code} stockName={name} />
                    </div>
                  </div>
                ) : null
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 포지션 섹션 */}
      <Card>
          <CardHeader className="flex justify-between items-center">
            <h2 className="text-lg font-semibold">포지션</h2>
            <Button size="sm" onClick={() => setShowAddPosition(true)}>
              + 포지션 추가
            </Button>
          </CardHeader>
          <CardContent>
            {currentIdea.positions.length === 0 ? (
              <p className="text-gray-500 dark:text-t-text-muted text-center py-4">포지션이 없습니다.</p>
            ) : (
              <div className="divide-y divide-gray-200 dark:divide-t-border">
                {currentIdea.positions.map((pos) => (
                  <div key={pos.id} className="py-4 flex justify-between items-center">
                    <div>
                      <div className="font-medium">
                        {pos.stock_name || pos.ticker}
                        {pos.stock_name && (
                          <span className="text-gray-400 text-sm ml-1">({pos.ticker})</span>
                        )}
                      </div>
                      <div className="text-sm text-gray-500 dark:text-t-text-muted">
                        {pos.quantity}주 @ {Number(pos.entry_price).toLocaleString()}원
                        <span className="mx-1">·</span>
                        투자금 {(Number(pos.entry_price) * pos.quantity).toLocaleString()}원
                      </div>
                      <div className="text-sm text-gray-500 dark:text-t-text-muted">
                        보유일: {pos.days_held}일
                      </div>
                    </div>
                  <div className="flex items-center gap-4">
                    {pos.is_open ? (
                      <>
                        <div className="text-right mr-2">
                          {pos.current_price != null ? (
                            <>
                              <div className="text-sm text-gray-600 dark:text-t-text-muted">
                                현재가: {Number(pos.current_price).toLocaleString()}원
                              </div>
                              {pos.unrealized_return_pct != null && (
                                <div className={`text-sm font-medium ${pos.unrealized_return_pct >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                                  {pos.unrealized_return_pct >= 0 ? '+' : ''}{pos.unrealized_return_pct.toFixed(2)}%
                                  <span className="text-gray-500 dark:text-t-text-muted font-normal ml-1">
                                    ({pos.unrealized_profit != null && pos.unrealized_profit >= 0 ? '+' : ''}
                                    {pos.unrealized_profit?.toLocaleString()}원)
                                  </span>
                                </div>
                              )}
                            </>
                          ) : (
                            <span className="text-sm text-gray-400">현재가 조회 중...</span>
                          )}
                        </div>
                        <Badge variant="success">보유 중</Badge>
                        <Button size="sm" variant="ghost" onClick={() => setShowAddBuy(pos.id)}>
                          추가매수
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setShowPartialExit(pos.id)}>
                          부분매도
                        </Button>
                        <Button size="sm" variant="secondary" onClick={() => setShowExitPosition(pos.id)}>
                          전량청산
                        </Button>
                      </>
                    ) : (
                      <div className="text-right">
                        <Badge variant="default">청산됨</Badge>
                        <div className="text-sm mt-1">
                          {Number(pos.exit_price).toLocaleString()}원
                          {pos.realized_return_pct != null && (
                            <span
                              className={
                                pos.realized_return_pct >= 0 ? 'text-red-500 ml-2' : 'text-blue-500 ml-2'
                              }
                            >
                              {pos.realized_return_pct >= 0 ? '+' : ''}
                              {pos.realized_return_pct.toFixed(2)}%
                            </span>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
          </CardContent>
        </Card>

      {/* 모달 컴포넌트들 */}
      <AddPositionModal
        isOpen={showAddPosition}
        onClose={() => setShowAddPosition(false)}
        onSubmit={handleAddPosition}
        tickers={currentIdea?.tickers}
      />
      <ExitPositionModal
        isOpen={showExitPosition !== null}
        onClose={() => setShowExitPosition(null)}
        onSubmit={handleExitPosition}
      />
      <AddBuyModal
        isOpen={showAddBuy !== null}
        onClose={() => setShowAddBuy(null)}
        onSubmit={handleAddBuy}
        position={activeAddBuyPosition}
      />
      <PartialExitModal
        isOpen={showPartialExit !== null}
        onClose={() => setShowPartialExit(null)}
        onSubmit={handlePartialExit}
        position={activePartialExitPosition}
      />
      <EditIdeaModal
        isOpen={showEditIdea}
        onClose={() => setShowEditIdea(false)}
        onSubmit={handleEditIdea}
        idea={currentIdea}
      />
      <ExitCheckModal
        isOpen={showExitCheck}
        onClose={() => setShowExitCheck(false)}
        result={exitCheckResult}
      />
    </div>
  )
}
