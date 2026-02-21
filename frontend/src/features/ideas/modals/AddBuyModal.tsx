import { useState } from 'react'
import Modal from '../../../components/ui/Modal'
import Input from '../../../components/ui/Input'
import Button from '../../../components/ui/Button'
import type { PositionAddBuy, Position } from '../../../types/idea'

interface Props {
  isOpen: boolean
  onClose: () => void
  onSubmit: (form: PositionAddBuy) => Promise<void>
  position: Position | null
}

export default function AddBuyModal({ isOpen, onClose, onSubmit, position }: Props) {
  const today = new Date().toISOString().split('T')[0]
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState<PositionAddBuy>({
    price: 0,
    quantity: 0,
    buy_date: today,
  })

  const handleSubmit = async () => {
    setLoading(true)
    try {
      await onSubmit(form)
      setForm({ price: 0, quantity: 0, buy_date: today })
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="추가매수">
      <div className="space-y-4">
        {position && (
          <div className="p-3 bg-gray-50 rounded-lg text-sm">
            <div className="font-medium mb-1">{position.stock_name || position.ticker}</div>
            <div className="text-gray-600">
              현재 보유: {position.quantity.toLocaleString()}주
              @ {Number(position.entry_price).toLocaleString()}원
            </div>
          </div>
        )}
        <Input
          label="추가 매수가"
          type="number"
          value={form.price || ''}
          onChange={(e) => setForm({ ...form, price: parseFloat(e.target.value) || 0 })}
          placeholder="추가 매수한 가격"
        />
        <Input
          label="추가 수량"
          type="number"
          value={form.quantity || ''}
          onChange={(e) => setForm({ ...form, quantity: parseInt(e.target.value) || 0 })}
          placeholder="추가 매수한 수량"
        />
        <Input
          label="매수일"
          type="date"
          value={form.buy_date || today}
          max={today}
          onChange={(e) => setForm({ ...form, buy_date: e.target.value })}
        />
        {form.price > 0 && form.quantity > 0 && position && (
          <div className="p-3 bg-blue-50 rounded-lg text-sm">
            <div className="font-medium text-blue-800">예상 결과</div>
            {(() => {
              const oldTotal = Number(position.entry_price) * position.quantity
              const newTotal = form.price * form.quantity
              const totalQty = position.quantity + form.quantity
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
          <Button variant="ghost" onClick={onClose}>취소</Button>
          <Button onClick={handleSubmit} loading={loading}>추가매수</Button>
        </div>
      </div>
    </Modal>
  )
}
