import { useState } from 'react'
import Modal from '../../../components/ui/Modal'
import Input from '../../../components/ui/Input'
import Select from '../../../components/ui/Select'
import Button from '../../../components/ui/Button'
import type { PositionExit } from '../../../types/idea'

interface Props {
  isOpen: boolean
  onClose: () => void
  onSubmit: (form: PositionExit) => Promise<void>
}

export default function ExitPositionModal({ isOpen, onClose, onSubmit }: Props) {
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState<PositionExit>({
    exit_price: 0,
    exit_reason: '',
  })

  const handleSubmit = async () => {
    setLoading(true)
    try {
      await onSubmit(form)
      setForm({ exit_price: 0, exit_reason: '' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="포지션 청산">
      <div className="space-y-4">
        <Input
          label="청산가"
          type="number"
          value={form.exit_price || ''}
          onChange={(e) => setForm({ ...form, exit_price: parseFloat(e.target.value) || 0 })}
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
          value={form.exit_reason || ''}
          onChange={(e) => setForm({ ...form, exit_reason: e.target.value })}
        />
        <div className="flex justify-end gap-2 mt-4">
          <Button variant="ghost" onClick={onClose}>취소</Button>
          <Button onClick={handleSubmit} loading={loading}>청산</Button>
        </div>
      </div>
    </Modal>
  )
}
