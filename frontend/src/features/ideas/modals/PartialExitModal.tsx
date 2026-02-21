import { useState } from 'react'
import Modal from '../../../components/ui/Modal'
import Input from '../../../components/ui/Input'
import Select from '../../../components/ui/Select'
import Button from '../../../components/ui/Button'
import type { PositionPartialExit, Position } from '../../../types/idea'

interface Props {
  isOpen: boolean
  onClose: () => void
  onSubmit: (form: PositionPartialExit) => Promise<void>
  position: Position | null
}

export default function PartialExitModal({ isOpen, onClose, onSubmit, position }: Props) {
  const today = new Date().toISOString().split('T')[0]
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState<PositionPartialExit>({
    exit_price: 0,
    quantity: 0,
    exit_date: today,
    exit_reason: '',
  })

  const handleSubmit = async () => {
    setLoading(true)
    try {
      await onSubmit(form)
      setForm({ exit_price: 0, quantity: 0, exit_date: today, exit_reason: '' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="부분매도">
      <div className="space-y-4">
        {position && (
          <div className="p-3 bg-gray-50 dark:bg-t-bg-elevated rounded-lg text-sm">
            <div className="font-medium mb-1 dark:text-t-text-primary">{position.stock_name || position.ticker}</div>
            <div className="text-gray-600 dark:text-t-text-muted">
              현재 보유: {position.quantity.toLocaleString()}주
              @ {Number(position.entry_price).toLocaleString()}원
            </div>
          </div>
        )}
        <Input
          label="매도가"
          type="number"
          value={form.exit_price || ''}
          onChange={(e) => setForm({ ...form, exit_price: parseFloat(e.target.value) || 0 })}
          placeholder="매도한 가격"
        />
        <Input
          label="매도 수량"
          type="number"
          value={form.quantity || ''}
          onChange={(e) => setForm({ ...form, quantity: parseInt(e.target.value) || 0 })}
          placeholder="매도할 수량"
        />
        <Input
          label="매도일"
          type="date"
          value={form.exit_date || today}
          max={today}
          onChange={(e) => setForm({ ...form, exit_date: e.target.value })}
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
          value={form.exit_reason || ''}
          onChange={(e) => setForm({ ...form, exit_reason: e.target.value })}
        />
        {form.exit_price > 0 && form.quantity > 0 && position && (
          <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg text-sm">
            <div className="font-medium text-blue-800 dark:text-blue-300">예상 결과</div>
            {(() => {
              const entryPrice = Number(position.entry_price)
              const profit = (form.exit_price - entryPrice) * form.quantity
              const returnPct = ((form.exit_price - entryPrice) / entryPrice) * 100
              const remainQty = position.quantity - form.quantity
              return (
                <>
                  <div className={`mt-1 ${profit >= 0 ? 'text-red-600' : 'text-blue-600'}`}>
                    실현 손익: {profit >= 0 ? '+' : ''}{Math.round(profit).toLocaleString()}원
                    ({returnPct >= 0 ? '+' : ''}{returnPct.toFixed(2)}%)
                  </div>
                  <div className="text-blue-700 dark:text-blue-300">
                    잔여 수량: {remainQty.toLocaleString()}주
                    {remainQty === 0 && ' (전량 청산)'}
                  </div>
                </>
              )
            })()}
          </div>
        )}
        <div className="flex justify-end gap-2 mt-4">
          <Button variant="ghost" onClick={onClose}>취소</Button>
          <Button onClick={handleSubmit} loading={loading}>부분매도</Button>
        </div>
      </div>
    </Modal>
  )
}
