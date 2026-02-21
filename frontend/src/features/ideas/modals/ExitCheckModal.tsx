import Modal from '../../../components/ui/Modal'
import Button from '../../../components/ui/Button'
import type { ExitCheckResult } from '../../../types/idea'

interface Props {
  isOpen: boolean
  onClose: () => void
  result: ExitCheckResult | null
}

export default function ExitCheckModal({ isOpen, onClose, result }: Props) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="청산 체크리스트" size="lg">
      {result && (
        <div className="space-y-4">
          <div className={`p-4 rounded-lg ${result.should_exit ? 'bg-green-50' : 'bg-yellow-50'}`}>
            <p className="font-medium">
              {result.should_exit
                ? '청산 조건을 충족합니다.'
                : '청산 조건을 충족하지 않습니다.'}
            </p>
          </div>

          <div className="space-y-2">
            <h4 className="font-medium">체크리스트:</h4>
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className={result.reasons.fundamental_broken ? 'text-red-600' : 'text-gray-400'}>
                  {result.reasons.fundamental_broken ? '!' : '-'}
                </span>
                <span>펀더멘탈 손상</span>
              </div>
              <div className="flex items-center gap-2">
                <span className={result.reasons.time_expired ? 'text-red-600' : 'text-gray-400'}>
                  {result.reasons.time_expired ? '!' : '-'}
                </span>
                <span>기간 만료</span>
              </div>
            </div>
          </div>

          {result.warnings.length > 0 && (
            <div className="p-4 bg-yellow-50 rounded-lg">
              <h4 className="font-medium text-yellow-800 mb-2">경고</h4>
              {result.warnings.map((warning, i) => (
                <p key={i} className="text-yellow-700">{warning}</p>
              ))}
            </div>
          )}

          {result.fomo_stats && (
            <div className="p-4 bg-blue-50 rounded-lg">
              <h4 className="font-medium text-blue-800 mb-2">과거 FOMO 청산 통계</h4>
              <p className="text-blue-700">{result.fomo_stats.message}</p>
            </div>
          )}

          <div className="flex justify-end">
            <Button onClick={onClose}>확인</Button>
          </div>
        </div>
      )}
    </Modal>
  )
}
