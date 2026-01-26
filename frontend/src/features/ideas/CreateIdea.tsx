import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardFooter } from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Input from '../../components/ui/Input'
import Select from '../../components/ui/Select'
import MarkdownEditor from '../../components/ui/MarkdownEditor'
import TickerSearch from '../../components/ui/TickerSearch'
import { ideaApi } from '../../services/api'
import type { IdeaCreate, IdeaType, PositionCreate } from '../../types/idea'

interface Stock {
  code: string
  name: string
}

interface PositionInput extends PositionCreate {
  stock_name?: string
}

export default function CreateIdea() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 오늘 날짜 (YYYY-MM-DD 형식)
  const today = new Date().toISOString().split('T')[0]
  const [selectedDate, setSelectedDate] = useState(today)

  const [formData, setFormData] = useState<IdeaCreate>({
    type: 'research',
    sector: '',
    tickers: [],
    thesis: '',
    expected_timeframe_days: 90,
    target_return_pct: 20,
    tags: [],
  })

  // 포지션 입력 옵션
  const [addPosition, setAddPosition] = useState(false)
  const [positionData, setPositionData] = useState<PositionInput>({
    ticker: '',
    entry_price: 0,
    quantity: 0,
  })

  const handleAddTicker = (stock: Stock) => {
    const tickerLabel = `${stock.name}(${stock.code})`
    if (!formData.tickers.includes(tickerLabel)) {
      setFormData({
        ...formData,
        tickers: [...formData.tickers, tickerLabel],
      })
      // 첫 번째 종목이면 포지션 기본값으로 설정
      if (formData.tickers.length === 0 && addPosition) {
        setPositionData({
          ...positionData,
          ticker: stock.code,
          stock_name: stock.name,
        })
      }
    }
  }

  const handleRemoveTicker = (ticker: string) => {
    setFormData({
      ...formData,
      tickers: formData.tickers.filter((t) => t !== ticker),
    })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      // 오늘이 아닌 날짜를 선택한 경우에만 created_at 전달
      const submitData: IdeaCreate = { ...formData }
      if (selectedDate !== today) {
        submitData.created_at = new Date(selectedDate).toISOString()
      }

      const idea = await ideaApi.create(submitData)

      // 포지션 추가 옵션이 활성화되어 있고 필수값이 있으면 포지션 생성
      if (addPosition && positionData.ticker && positionData.entry_price > 0 && positionData.quantity > 0) {
        try {
          await ideaApi.createPosition(idea.id, {
            ticker: positionData.ticker,
            entry_price: positionData.entry_price,
            quantity: positionData.quantity,
            entry_date: selectedDate !== today ? selectedDate : undefined,
          })
        } catch (posError) {
          console.error('포지션 생성 실패:', posError)
          // 포지션 실패해도 아이디어는 생성됨
        }
      }

      navigate(`/ideas/${idea.id}`)
    } catch (err) {
      setError('아이디어 생성에 실패했습니다.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">새 아이디어 생성</h1>

      <Card>
        <form onSubmit={handleSubmit}>
          <CardHeader>
            <h2 className="text-lg font-semibold">기본 정보</h2>
          </CardHeader>

          <CardContent className="space-y-4">
            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">
                {error}
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <Select
                label="유형"
                options={[
                  { value: 'research', label: '리서치 (기업 분석 기반)' },
                  { value: 'chart', label: '차트 (기술적 분석 기반)' },
                ]}
                value={formData.type}
                onChange={(e) => setFormData({ ...formData, type: e.target.value as IdeaType })}
              />

              <Input
                label="기준일"
                type="date"
                value={selectedDate}
                max={today}
                onChange={(e) => setSelectedDate(e.target.value)}
              />
            </div>

            <Input
              label="섹터"
              placeholder="예: 반도체, 바이오, IT"
              value={formData.sector || ''}
              onChange={(e) => setFormData({ ...formData, sector: e.target.value })}
            />

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                종목
              </label>
              <div className="mb-2">
                <TickerSearch
                  onSelect={handleAddTicker}
                  placeholder="종목명 또는 코드로 검색 (예: 삼성전자, 005930)"
                />
              </div>
              {formData.tickers.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {formData.tickers.map((ticker) => (
                    <span
                      key={ticker}
                      className="inline-flex items-center px-3 py-1 bg-primary-100 text-primary-800 rounded-full text-sm"
                    >
                      {ticker}
                      <button
                        type="button"
                        onClick={() => handleRemoveTicker(ticker)}
                        className="ml-2 text-primary-600 hover:text-primary-800 font-bold"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                투자 논리
              </label>
              <MarkdownEditor
                value={formData.thesis}
                onChange={(value) => setFormData({ ...formData, thesis: value })}
                placeholder="투자 논리를 작성하세요...&#10;&#10;이미지는 드래그앤드롭 또는 붙여넣기(Ctrl+V)로 추가할 수 있습니다."
                minHeight={300}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Input
                label="예상 기간 (일)"
                type="number"
                min={1}
                value={formData.expected_timeframe_days}
                onChange={(e) =>
                  setFormData({ ...formData, expected_timeframe_days: parseInt(e.target.value) || 0 })
                }
                required
              />
              <Input
                label="목표 수익률 (%)"
                type="number"
                min={0}
                step={0.1}
                value={formData.target_return_pct}
                onChange={(e) =>
                  setFormData({ ...formData, target_return_pct: parseFloat(e.target.value) || 0 })
                }
                required
              />
            </div>

            {/* 포지션 입력 옵션 */}
            <div className="border-t pt-4 mt-4">
              <label className="flex items-center gap-2 cursor-pointer mb-4">
                <input
                  type="checkbox"
                  checked={addPosition}
                  onChange={(e) => setAddPosition(e.target.checked)}
                  className="w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <span className="text-sm font-medium text-gray-700">포지션도 함께 등록</span>
              </label>

              {addPosition && (
                <div className="space-y-3 p-4 bg-gray-50 rounded-lg">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      종목 선택
                    </label>
                    <select
                      value={positionData.ticker}
                      onChange={(e) => {
                        const selected = formData.tickers.find(t => t.includes(e.target.value))
                        const name = selected?.replace(/\(\d{6}\)/, '').trim() || ''
                        setPositionData({ ...positionData, ticker: e.target.value, stock_name: name })
                      }}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                    >
                      <option value="">종목을 선택하세요</option>
                      {formData.tickers.map((ticker) => {
                        const match = ticker.match(/\((\d{6})\)/)
                        const code = match ? match[1] : ticker
                        return (
                          <option key={code} value={code}>
                            {ticker}
                          </option>
                        )
                      })}
                    </select>
                    {formData.tickers.length === 0 && (
                      <p className="text-xs text-gray-500 mt-1">먼저 위에서 종목을 추가하세요</p>
                    )}
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <Input
                      label="매수가 (원)"
                      type="number"
                      min={0}
                      value={positionData.entry_price || ''}
                      onChange={(e) =>
                        setPositionData({ ...positionData, entry_price: parseFloat(e.target.value) || 0 })
                      }
                      placeholder="예: 70000"
                    />
                    <Input
                      label="수량 (주)"
                      type="number"
                      min={0}
                      value={positionData.quantity || ''}
                      onChange={(e) =>
                        setPositionData({ ...positionData, quantity: parseInt(e.target.value) || 0 })
                      }
                      placeholder="예: 100"
                    />
                  </div>
                  {positionData.entry_price > 0 && positionData.quantity > 0 && (
                    <div className="text-sm text-gray-600">
                      총 매수금액:{' '}
                      <span className="font-medium">
                        {(positionData.entry_price * positionData.quantity).toLocaleString()}원
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          </CardContent>

          <CardFooter className="flex justify-end gap-3">
            <Button type="button" variant="ghost" onClick={() => navigate(-1)}>
              취소
            </Button>
            <Button type="submit" loading={loading}>
              아이디어 생성
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  )
}
