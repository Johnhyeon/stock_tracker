import { useState, useEffect, lazy, Suspense } from 'react'
import Modal from '../../../components/ui/Modal'
import Input from '../../../components/ui/Input'
import Button from '../../../components/ui/Button'
const MarkdownEditor = lazy(() => import('../../../components/ui/MarkdownEditor'))
import TickerSearch from '../../../components/ui/TickerSearch'
import type { IdeaUpdate, IdeaWithPositions } from '../../../types/idea'

interface Stock {
  code: string
  name: string
}

interface Props {
  isOpen: boolean
  onClose: () => void
  onSubmit: (form: IdeaUpdate) => Promise<void>
  idea: IdeaWithPositions | null
}

export default function EditIdeaModal({ isOpen, onClose, onSubmit, idea }: Props) {
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState<IdeaUpdate>({
    thesis: '',
    expected_timeframe_days: 0,
    target_return_pct: 0,
    sector: '',
  })

  useEffect(() => {
    if (idea && isOpen) {
      setForm({
        thesis: idea.thesis,
        expected_timeframe_days: idea.expected_timeframe_days,
        target_return_pct: Number(idea.target_return_pct),
        sector: idea.sector || '',
        tickers: idea.tickers,
        tags: idea.tags || [],
      })
    }
  }, [idea, isOpen])

  const handleSubmit = async () => {
    setLoading(true)
    try {
      await onSubmit(form)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="아이디어 수정" size="lg">
      <div className="space-y-4">
        <Input
          label="섹터"
          value={form.sector || ''}
          onChange={(e) => setForm({ ...form, sector: e.target.value })}
          placeholder="예: 반도체, 2차전지"
        />

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">종목</label>
          <div className="mb-2">
            <TickerSearch
              onSelect={(stock: Stock) => {
                const tickerLabel = `${stock.name}(${stock.code})`
                const currentTickers = form.tickers || []
                if (!currentTickers.includes(tickerLabel)) {
                  setForm({ ...form, tickers: [...currentTickers, tickerLabel] })
                }
              }}
              placeholder="종목명 또는 코드로 검색"
            />
          </div>
          {form.tickers && form.tickers.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {form.tickers.map((ticker) => (
                <span
                  key={ticker}
                  className="inline-flex items-center px-3 py-1 bg-primary-100 text-primary-800 rounded-full text-sm"
                >
                  {ticker}
                  <button
                    type="button"
                    onClick={() =>
                      setForm({
                        ...form,
                        tickers: form.tickers?.filter((t) => t !== ticker),
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
            value={form.target_return_pct || ''}
            onChange={(e) =>
              setForm({ ...form, target_return_pct: parseFloat(e.target.value) || 0 })
            }
          />
          <Input
            label="예상 기간 (일)"
            type="number"
            value={form.expected_timeframe_days || ''}
            onChange={(e) =>
              setForm({ ...form, expected_timeframe_days: parseInt(e.target.value) || 0 })
            }
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">투자 논리</label>
          <Suspense fallback={<div className="h-[200px] flex items-center justify-center text-gray-400 dark:text-gray-600 border rounded-lg">에디터 로딩중...</div>}>
            <MarkdownEditor
              value={form.thesis || ''}
              onChange={(value) => setForm({ ...form, thesis: value })}
              placeholder="투자 논리를 마크다운 형식으로 작성하세요"
              minHeight={200}
            />
          </Suspense>
        </div>

        <div className="flex justify-end gap-2 mt-4">
          <Button variant="ghost" onClick={onClose}>취소</Button>
          <Button onClick={handleSubmit} loading={loading}>저장</Button>
        </div>
      </div>
    </Modal>
  )
}
