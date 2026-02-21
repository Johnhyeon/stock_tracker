import { useState, useMemo } from 'react'
import Modal from '../../../components/ui/Modal'
import Input from '../../../components/ui/Input'
import Button from '../../../components/ui/Button'
import type { PositionCreate } from '../../../types/idea'

interface Props {
  isOpen: boolean
  onClose: () => void
  onSubmit: (form: PositionCreate) => Promise<void>
  tickers?: string[]
}

/** "삼성전자(005930)" → { code: "005930", name: "삼성전자", label: "삼성전자(005930)" } */
function parseTicker(ticker: string) {
  const match = ticker.match(/^(.+)\(([A-Za-z0-9]{6})\)$/)
  if (match) return { code: match[2], name: match[1], label: ticker }
  return { code: ticker, name: ticker, label: ticker }
}

export default function AddPositionModal({ isOpen, onClose, onSubmit, tickers }: Props) {
  const today = new Date().toISOString().split('T')[0]
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState<PositionCreate>({
    ticker: '',
    entry_price: 0,
    quantity: 0,
    entry_date: today,
  })

  const stockOptions = useMemo(() => (tickers || []).map(parseTicker), [tickers])

  const handleSelect = (code: string) => {
    setForm(prev => ({ ...prev, ticker: code }))
  }

  const handleSubmit = async () => {
    setLoading(true)
    try {
      await onSubmit(form)
      setForm({ ticker: '', entry_price: 0, quantity: 0, entry_date: today })
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="포지션 추가">
      <div className="space-y-4">
        {/* 아이디어 종목 드롭다운 */}
        {stockOptions.length > 0 && (
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-t-text-secondary mb-1">
              아이디어 종목
            </label>
            <div className="flex flex-wrap gap-1.5">
              {stockOptions.map(opt => (
                <button
                  key={opt.code}
                  type="button"
                  onClick={() => handleSelect(opt.code)}
                  className={`px-2.5 py-1.5 text-xs rounded-lg border transition-colors ${
                    form.ticker === opt.code
                      ? 'bg-primary-500 text-white border-primary-500'
                      : 'bg-white dark:bg-t-bg border-gray-300 dark:border-t-border text-gray-700 dark:text-t-text-secondary hover:border-primary-400 hover:text-primary-500'
                  }`}
                >
                  <span className="font-medium">{opt.name}</span>
                  <span className="text-[10px] ml-1 opacity-70">{opt.code}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        <Input
          label="종목 코드"
          value={form.ticker}
          onChange={(e) => setForm({ ...form, ticker: e.target.value.toUpperCase() })}
          placeholder={stockOptions.length > 0 ? '위에서 선택하거나 직접 입력' : '종목코드 6자리'}
        />
        <Input
          label="매수가"
          type="number"
          value={form.entry_price || ''}
          onChange={(e) => setForm({ ...form, entry_price: parseFloat(e.target.value) || 0 })}
        />
        <Input
          label="수량"
          type="number"
          value={form.quantity || ''}
          onChange={(e) => setForm({ ...form, quantity: parseInt(e.target.value) || 0 })}
        />
        <Input
          label="매수일"
          type="date"
          value={form.entry_date || today}
          max={today}
          onChange={(e) => setForm({ ...form, entry_date: e.target.value })}
        />
        <div className="flex justify-end gap-2 mt-4">
          <Button variant="ghost" onClick={onClose}>취소</Button>
          <Button onClick={handleSubmit} loading={loading}>추가</Button>
        </div>
      </div>
    </Modal>
  )
}
