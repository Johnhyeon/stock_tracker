import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useIdeaStore } from '../../store/useIdeaStore'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Badge from '../../components/ui/Badge'
import Modal from '../../components/ui/Modal'
import Input from '../../components/ui/Input'
import Select from '../../components/ui/Select'
import MarkdownViewer from '../../components/ui/MarkdownViewer'
import MarkdownEditor from '../../components/ui/MarkdownEditor'
import TickerSearch from '../../components/ui/TickerSearch'
import { IdeaStockChart } from '../../components/IdeaStockChart'
import { StockFlowPanel } from '../../components/StockFlowPanel'
import { ideaApi, positionApi } from '../../services/api'
import type { PositionCreate, PositionExit, PositionAddBuy, PositionPartialExit, ExitCheckResult, FundamentalHealth, IdeaUpdate } from '../../types/idea'

interface Stock {
  code: string
  name: string
}

// 종목코드 파싱 유틸리티
const extractStockCode = (ticker: string): string | null => {
  const match = ticker.match(/\((\d{6})\)/)
  return match ? match[1] : null
}

const extractStockName = (ticker: string): string => {
  const match = ticker.match(/^(.+)\(\d{6}\)$/)
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
  const [showAddBuy, setShowAddBuy] = useState<string | null>(null)  // 추가매수 모달용 position id
  const [showPartialExit, setShowPartialExit] = useState<string | null>(null)  // 부분매도 모달용 position id
  const [showExitCheck, setShowExitCheck] = useState(false)
  const [showEditIdea, setShowEditIdea] = useState(false)
  const [exitCheckResult, setExitCheckResult] = useState<ExitCheckResult | null>(null)
  const [actionLoading, setActionLoading] = useState(false)

  // 오늘 날짜 (YYYY-MM-DD 형식)
  const today = new Date().toISOString().split('T')[0]

  const [positionForm, setPositionForm] = useState<PositionCreate>({
    ticker: '',
    entry_price: 0,
    quantity: 0,
    entry_date: today,
  })

  const [exitForm, setExitForm] = useState<PositionExit>({
    exit_price: 0,
    exit_reason: '',
  })

  const [addBuyForm, setAddBuyForm] = useState<PositionAddBuy>({
    price: 0,
    quantity: 0,
    buy_date: today,
  })

  const [partialExitForm, setPartialExitForm] = useState<PositionPartialExit>({
    exit_price: 0,
    quantity: 0,
    exit_date: today,
    exit_reason: '',
  })

  const [editForm, setEditForm] = useState<IdeaUpdate>({
    thesis: '',
    expected_timeframe_days: 0,
    target_return_pct: 0,
    sector: '',
  })

  useEffect(() => {
    if (id) fetchIdea(id)
  }, [id, fetchIdea])

  const handleAddPosition = async () => {
    if (!id) return
    setActionLoading(true)
    try {
      await ideaApi.createPosition(id, positionForm)
      fetchIdea(id)
      setShowAddPosition(false)
      setPositionForm({ ticker: '', entry_price: 0, quantity: 0, entry_date: today })
    } catch (err) {
      console.error(err)
    } finally {
      setActionLoading(false)
    }
  }

  const handleExitPosition = async () => {
    if (!showExitPosition || !id) return
    setActionLoading(true)
    try {
      await positionApi.exit(showExitPosition, exitForm)
      fetchIdea(id)
      setShowExitPosition(null)
      setExitForm({ exit_price: 0, exit_reason: '' })
    } catch (err) {
      console.error(err)
    } finally {
      setActionLoading(false)
    }
  }

  const handleAddBuy = async () => {
    if (!showAddBuy || !id) return
    setActionLoading(true)
    try {
      await positionApi.addBuy(showAddBuy, addBuyForm)
      fetchIdea(id)
      setShowAddBuy(null)
      setAddBuyForm({ price: 0, quantity: 0, buy_date: today })
    } catch (err) {
      console.error(err)
    } finally {
      setActionLoading(false)
    }
  }

  const handlePartialExit = async () => {
    if (!showPartialExit || !id) return
    setActionLoading(true)
    try {
      await positionApi.partialExit(showPartialExit, partialExitForm)
      fetchIdea(id)
      setShowPartialExit(null)
      setPartialExitForm({ exit_price: 0, quantity: 0, exit_date: today, exit_reason: '' })
    } catch (err) {
      console.error(err)
    } finally {
      setActionLoading(false)
    }
  }

  const handleCheckExit = async () => {
    if (!id) return
    setActionLoading(true)
    try {
      const result = await ideaApi.checkExit(id)
      setExitCheckResult(result)
      setShowExitCheck(true)
    } catch (err) {
      console.error(err)
    } finally {
      setActionLoading(false)
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

  const handleOpenEdit = () => {
    if (!currentIdea) return
    setEditForm({
      thesis: currentIdea.thesis,
      expected_timeframe_days: currentIdea.expected_timeframe_days,
      target_return_pct: Number(currentIdea.target_return_pct),
      sector: currentIdea.sector || '',
      tickers: currentIdea.tickers,
      tags: currentIdea.tags || [],
    })
    setShowEditIdea(true)
  }

  const handleEditIdea = async () => {
    if (!id) return
    setActionLoading(true)
    try {
      await ideaApi.update(id, editForm)
      fetchIdea(id)
      setShowEditIdea(false)
    } catch (err) {
      console.error(err)
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) return <div className="text-center py-10">로딩 중...</div>
  if (error) return <div className="text-center py-10 text-red-600">{error}</div>
  if (!currentIdea) return <div className="text-center py-10">아이디어를 찾을 수 없습니다.</div>

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
          <h1 className="text-2xl font-bold text-gray-900">
            {currentIdea.tickers.join(', ') || '종목 미지정'}
          </h1>
          {currentIdea.sector && <p className="text-gray-500">{currentIdea.sector}</p>}
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={handleOpenEdit}>
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

      <div className="grid gap-6 md:grid-cols-3 mb-6">
        <Card>
          <CardContent>
            <div className="text-sm text-gray-500">목표 수익률</div>
            <div className="text-2xl font-bold text-primary-600">
              {Number(currentIdea.target_return_pct)}%
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="text-sm text-gray-500">예상 기간</div>
            <div className="text-2xl font-bold">{currentIdea.expected_timeframe_days}일</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="text-sm text-gray-500">투자 금액</div>
            <div className="text-2xl font-bold">
              {currentIdea.total_invested?.toLocaleString() || 0}원
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="mb-6 flex items-center gap-3">
        <span className="text-sm text-gray-600">펀더멘탈:</span>
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
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
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
              <span className="text-sm text-gray-500">
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

                // 해당 종목의 포지션들 찾기
                const stockPositions = currentIdea.positions.filter(
                  (p) => p.ticker === code || p.ticker.includes(code || '')
                )

                // 평균 매수가 계산 (가중평균)
                let avgEntryPrice: number | undefined
                if (stockPositions.length > 0) {
                  const totalQty = stockPositions.reduce((sum, p) => sum + p.quantity, 0)
                  const totalValue = stockPositions.reduce(
                    (sum, p) => sum + Number(p.entry_price) * p.quantity,
                    0
                  )
                  avgEntryPrice = totalQty > 0 ? totalValue / totalQty : undefined
                }

                // 매수 마커 생성
                const entryMarkers = stockPositions
                  .filter((p) => p.entry_date)
                  .map((p) => ({
                    date: p.entry_date as string,
                    price: Number(p.entry_price),
                    quantity: p.quantity,
                  }))

                return code ? (
                  <div key={code} className="grid gap-4 md:grid-cols-3">
                    {/* 차트 (2/3) */}
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
                    {/* 수급 패널 (1/3) */}
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
              <p className="text-gray-500 text-center py-4">포지션이 없습니다.</p>
            ) : (
              <div className="divide-y divide-gray-200">
                {currentIdea.positions.map((pos) => (
                  <div key={pos.id} className="py-4 flex justify-between items-center">
                    <div>
                      <div className="font-medium">
                        {pos.stock_name || pos.ticker}
                        {pos.stock_name && (
                          <span className="text-gray-400 text-sm ml-1">({pos.ticker})</span>
                        )}
                      </div>
                      <div className="text-sm text-gray-500">
                        {pos.quantity}주 @ {Number(pos.entry_price).toLocaleString()}원
                        <span className="mx-1">·</span>
                        투자금 {(Number(pos.entry_price) * pos.quantity).toLocaleString()}원
                      </div>
                      <div className="text-sm text-gray-500">
                        보유일: {pos.days_held}일
                      </div>
                    </div>
                  <div className="flex items-center gap-4">
                    {pos.is_open ? (
                      <>
                        <div className="text-right mr-2">
                          {pos.current_price != null ? (
                            <>
                              <div className="text-sm text-gray-600">
                                현재가: {Number(pos.current_price).toLocaleString()}원
                              </div>
                              {pos.unrealized_return_pct != null && (
                                <div className={`text-sm font-medium ${pos.unrealized_return_pct >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                                  {pos.unrealized_return_pct >= 0 ? '+' : ''}{pos.unrealized_return_pct.toFixed(2)}%
                                  <span className="text-gray-500 font-normal ml-1">
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
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setShowAddBuy(pos.id)}
                        >
                          추가매수
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setShowPartialExit(pos.id)}
                        >
                          부분매도
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => setShowExitPosition(pos.id)}
                        >
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

      <Modal isOpen={showAddPosition} onClose={() => setShowAddPosition(false)} title="포지션 추가">
        <div className="space-y-4">
          <Input
            label="종목 코드"
            value={positionForm.ticker}
            onChange={(e) => setPositionForm({ ...positionForm, ticker: e.target.value.toUpperCase() })}
          />
          <Input
            label="매수가"
            type="number"
            value={positionForm.entry_price || ''}
            onChange={(e) =>
              setPositionForm({ ...positionForm, entry_price: parseFloat(e.target.value) || 0 })
            }
          />
          <Input
            label="수량"
            type="number"
            value={positionForm.quantity || ''}
            onChange={(e) =>
              setPositionForm({ ...positionForm, quantity: parseInt(e.target.value) || 0 })
            }
          />
          <Input
            label="매수일"
            type="date"
            value={positionForm.entry_date || today}
            max={today}
            onChange={(e) =>
              setPositionForm({ ...positionForm, entry_date: e.target.value })
            }
          />
          <div className="flex justify-end gap-2 mt-4">
            <Button variant="ghost" onClick={() => setShowAddPosition(false)}>
              취소
            </Button>
            <Button onClick={handleAddPosition} loading={actionLoading}>
              추가
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={showExitPosition !== null}
        onClose={() => setShowExitPosition(null)}
        title="포지션 청산"
      >
        <div className="space-y-4">
          <Input
            label="청산가"
            type="number"
            value={exitForm.exit_price || ''}
            onChange={(e) => setExitForm({ ...exitForm, exit_price: parseFloat(e.target.value) || 0 })}
          />
          <Select
            label="청산 사유"
            options={[
              { value: '', label: '선택' },
              { value: 'target_reached', label: '목표 달성' },
              { value: 'stop_loss', label: '손절' },
              { value: 'fundamental_broken', label: '펀더멘탈 손상' },
              { value: 'time_expired', label: '기간 만료' },
              { value: 'fomo', label: 'FOMO (조기 청산)' },
              { value: 'other', label: '기타' },
            ]}
            value={exitForm.exit_reason || ''}
            onChange={(e) => setExitForm({ ...exitForm, exit_reason: e.target.value })}
          />
          <div className="flex justify-end gap-2 mt-4">
            <Button variant="ghost" onClick={() => setShowExitPosition(null)}>
              취소
            </Button>
            <Button onClick={handleExitPosition} loading={actionLoading}>
              청산
            </Button>
          </div>
        </div>
      </Modal>

      {/* 추가매수 모달 */}
      <Modal
        isOpen={showAddBuy !== null}
        onClose={() => setShowAddBuy(null)}
        title="추가매수"
      >
        <div className="space-y-4">
          {showAddBuy && currentIdea?.positions.find(p => p.id === showAddBuy) && (
            <div className="p-3 bg-gray-50 rounded-lg text-sm">
              <div className="font-medium mb-1">
                {currentIdea.positions.find(p => p.id === showAddBuy)?.stock_name ||
                 currentIdea.positions.find(p => p.id === showAddBuy)?.ticker}
              </div>
              <div className="text-gray-600">
                현재 보유: {currentIdea.positions.find(p => p.id === showAddBuy)?.quantity.toLocaleString()}주
                @ {Number(currentIdea.positions.find(p => p.id === showAddBuy)?.entry_price).toLocaleString()}원
              </div>
            </div>
          )}
          <Input
            label="추가 매수가"
            type="number"
            value={addBuyForm.price || ''}
            onChange={(e) => setAddBuyForm({ ...addBuyForm, price: parseFloat(e.target.value) || 0 })}
            placeholder="추가 매수한 가격"
          />
          <Input
            label="추가 수량"
            type="number"
            value={addBuyForm.quantity || ''}
            onChange={(e) => setAddBuyForm({ ...addBuyForm, quantity: parseInt(e.target.value) || 0 })}
            placeholder="추가 매수한 수량"
          />
          <Input
            label="매수일"
            type="date"
            value={addBuyForm.buy_date || today}
            max={today}
            onChange={(e) => setAddBuyForm({ ...addBuyForm, buy_date: e.target.value })}
          />
          {addBuyForm.price > 0 && addBuyForm.quantity > 0 && showAddBuy && (
            <div className="p-3 bg-blue-50 rounded-lg text-sm">
              <div className="font-medium text-blue-800">예상 결과</div>
              {(() => {
                const pos = currentIdea?.positions.find(p => p.id === showAddBuy)
                if (!pos) return null
                const oldTotal = Number(pos.entry_price) * pos.quantity
                const newTotal = addBuyForm.price * addBuyForm.quantity
                const totalQty = pos.quantity + addBuyForm.quantity
                const newAvg = (oldTotal + newTotal) / totalQty
                return (
                  <div className="text-blue-700 mt-1">
                    새 평균단가: {Math.round(newAvg).toLocaleString()}원 /
                    총 수량: {totalQty.toLocaleString()}주
                  </div>
                )
              })()}
            </div>
          )}
          <div className="flex justify-end gap-2 mt-4">
            <Button variant="ghost" onClick={() => setShowAddBuy(null)}>
              취소
            </Button>
            <Button onClick={handleAddBuy} loading={actionLoading}>
              추가매수
            </Button>
          </div>
        </div>
      </Modal>

      {/* 부분매도 모달 */}
      <Modal
        isOpen={showPartialExit !== null}
        onClose={() => setShowPartialExit(null)}
        title="부분매도"
      >
        <div className="space-y-4">
          {showPartialExit && currentIdea?.positions.find(p => p.id === showPartialExit) && (
            <div className="p-3 bg-gray-50 rounded-lg text-sm">
              <div className="font-medium mb-1">
                {currentIdea.positions.find(p => p.id === showPartialExit)?.stock_name ||
                 currentIdea.positions.find(p => p.id === showPartialExit)?.ticker}
              </div>
              <div className="text-gray-600">
                현재 보유: {currentIdea.positions.find(p => p.id === showPartialExit)?.quantity.toLocaleString()}주
                @ {Number(currentIdea.positions.find(p => p.id === showPartialExit)?.entry_price).toLocaleString()}원
              </div>
            </div>
          )}
          <Input
            label="매도가"
            type="number"
            value={partialExitForm.exit_price || ''}
            onChange={(e) => setPartialExitForm({ ...partialExitForm, exit_price: parseFloat(e.target.value) || 0 })}
            placeholder="매도한 가격"
          />
          <Input
            label="매도 수량"
            type="number"
            value={partialExitForm.quantity || ''}
            onChange={(e) => setPartialExitForm({ ...partialExitForm, quantity: parseInt(e.target.value) || 0 })}
            placeholder="매도할 수량"
          />
          <Input
            label="매도일"
            type="date"
            value={partialExitForm.exit_date || today}
            max={today}
            onChange={(e) => setPartialExitForm({ ...partialExitForm, exit_date: e.target.value })}
          />
          <Select
            label="매도 사유"
            options={[
              { value: '', label: '선택' },
              { value: 'partial_profit', label: '일부 익절' },
              { value: 'rebalancing', label: '리밸런싱' },
              { value: 'risk_reduction', label: '리스크 축소' },
              { value: 'other', label: '기타' },
            ]}
            value={partialExitForm.exit_reason || ''}
            onChange={(e) => setPartialExitForm({ ...partialExitForm, exit_reason: e.target.value })}
          />
          {partialExitForm.exit_price > 0 && partialExitForm.quantity > 0 && showPartialExit && (
            <div className="p-3 bg-blue-50 rounded-lg text-sm">
              <div className="font-medium text-blue-800">예상 결과</div>
              {(() => {
                const pos = currentIdea?.positions.find(p => p.id === showPartialExit)
                if (!pos) return null
                const entryPrice = Number(pos.entry_price)
                const profit = (partialExitForm.exit_price - entryPrice) * partialExitForm.quantity
                const returnPct = ((partialExitForm.exit_price - entryPrice) / entryPrice) * 100
                const remainQty = pos.quantity - partialExitForm.quantity
                return (
                  <>
                    <div className={`mt-1 ${profit >= 0 ? 'text-red-600' : 'text-blue-600'}`}>
                      실현 손익: {profit >= 0 ? '+' : ''}{Math.round(profit).toLocaleString()}원
                      ({returnPct >= 0 ? '+' : ''}{returnPct.toFixed(2)}%)
                    </div>
                    <div className="text-blue-700">
                      잔여 수량: {remainQty.toLocaleString()}주
                      {remainQty === 0 && ' (전량 청산)'}
                    </div>
                  </>
                )
              })()}
            </div>
          )}
          <div className="flex justify-end gap-2 mt-4">
            <Button variant="ghost" onClick={() => setShowPartialExit(null)}>
              취소
            </Button>
            <Button onClick={handlePartialExit} loading={actionLoading}>
              부분매도
            </Button>
          </div>
        </div>
      </Modal>

      <Modal isOpen={showExitCheck} onClose={() => setShowExitCheck(false)} title="청산 체크리스트" size="lg">
        {exitCheckResult && (
          <div className="space-y-4">
            <div className={`p-4 rounded-lg ${exitCheckResult.should_exit ? 'bg-green-50' : 'bg-yellow-50'}`}>
              <p className="font-medium">
                {exitCheckResult.should_exit
                  ? '청산 조건을 충족합니다.'
                  : '청산 조건을 충족하지 않습니다.'}
              </p>
            </div>

            <div className="space-y-2">
              <h4 className="font-medium">체크리스트:</h4>
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className={exitCheckResult.reasons.fundamental_broken ? 'text-red-600' : 'text-gray-400'}>
                    {exitCheckResult.reasons.fundamental_broken ? '!' : '-'}
                  </span>
                  <span>펀더멘탈 손상</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={exitCheckResult.reasons.time_expired ? 'text-red-600' : 'text-gray-400'}>
                    {exitCheckResult.reasons.time_expired ? '!' : '-'}
                  </span>
                  <span>기간 만료</span>
                </div>
              </div>
            </div>

            {exitCheckResult.warnings.length > 0 && (
              <div className="p-4 bg-yellow-50 rounded-lg">
                <h4 className="font-medium text-yellow-800 mb-2">경고</h4>
                {exitCheckResult.warnings.map((warning, i) => (
                  <p key={i} className="text-yellow-700">
                    {warning}
                  </p>
                ))}
              </div>
            )}

            {exitCheckResult.fomo_stats && (
              <div className="p-4 bg-blue-50 rounded-lg">
                <h4 className="font-medium text-blue-800 mb-2">과거 FOMO 청산 통계</h4>
                <p className="text-blue-700">{exitCheckResult.fomo_stats.message}</p>
              </div>
            )}

            <div className="flex justify-end">
              <Button onClick={() => setShowExitCheck(false)}>확인</Button>
            </div>
          </div>
        )}
      </Modal>

      <Modal isOpen={showEditIdea} onClose={() => setShowEditIdea(false)} title="아이디어 수정" size="lg">
        <div className="space-y-4">
          <Input
            label="섹터"
            value={editForm.sector || ''}
            onChange={(e) => setEditForm({ ...editForm, sector: e.target.value })}
            placeholder="예: 반도체, 2차전지"
          />

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">종목</label>
            <div className="mb-2">
              <TickerSearch
                onSelect={(stock: Stock) => {
                  const tickerLabel = `${stock.name}(${stock.code})`
                  const currentTickers = editForm.tickers || []
                  if (!currentTickers.includes(tickerLabel)) {
                    setEditForm({ ...editForm, tickers: [...currentTickers, tickerLabel] })
                  }
                }}
                placeholder="종목명 또는 코드로 검색"
              />
            </div>
            {editForm.tickers && editForm.tickers.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {editForm.tickers.map((ticker) => (
                  <span
                    key={ticker}
                    className="inline-flex items-center px-3 py-1 bg-primary-100 text-primary-800 rounded-full text-sm"
                  >
                    {ticker}
                    <button
                      type="button"
                      onClick={() =>
                        setEditForm({
                          ...editForm,
                          tickers: editForm.tickers?.filter((t) => t !== ticker),
                        })
                      }
                      className="ml-2 text-primary-600 hover:text-primary-800 font-bold"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Input
              label="목표 수익률 (%)"
              type="number"
              value={editForm.target_return_pct || ''}
              onChange={(e) =>
                setEditForm({ ...editForm, target_return_pct: parseFloat(e.target.value) || 0 })
              }
            />
            <Input
              label="예상 기간 (일)"
              type="number"
              value={editForm.expected_timeframe_days || ''}
              onChange={(e) =>
                setEditForm({ ...editForm, expected_timeframe_days: parseInt(e.target.value) || 0 })
              }
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">투자 논리</label>
            <MarkdownEditor
              value={editForm.thesis || ''}
              onChange={(value) => setEditForm({ ...editForm, thesis: value })}
              placeholder="투자 논리를 마크다운 형식으로 작성하세요"
              minHeight={200}
            />
          </div>

          <div className="flex justify-end gap-2 mt-4">
            <Button variant="ghost" onClick={() => setShowEditIdea(false)}>
              취소
            </Button>
            <Button onClick={handleEditIdea} loading={actionLoading}>
              저장
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
