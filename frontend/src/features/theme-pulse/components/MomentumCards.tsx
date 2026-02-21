import type { ThemePulseItem } from '../../../types/theme_pulse'

interface Props {
  items: ThemePulseItem[]
}

function getMomentumGradient(momentum: number): string {
  if (momentum >= 50) return 'from-red-500 to-orange-500'
  if (momentum >= 20) return 'from-orange-400 to-amber-400'
  if (momentum >= 0) return 'from-amber-400 to-yellow-300'
  if (momentum >= -20) return 'from-blue-300 to-cyan-300'
  return 'from-blue-500 to-indigo-500'
}

function getMomentumLabel(momentum: number): string {
  if (momentum >= 50) return 'Surging'
  if (momentum >= 20) return 'Rising'
  if (momentum >= 0) return 'Stable'
  if (momentum >= -20) return 'Cooling'
  return 'Declining'
}

export default function MomentumCards({ items }: Props) {
  const top5 = items.slice(0, 5)

  return (
    <div className="flex gap-3 overflow-x-auto pb-2">
      {top5.map((item) => (
        <div
          key={item.theme_name}
          className={`flex-shrink-0 w-48 rounded-xl p-4 bg-gradient-to-br ${getMomentumGradient(item.momentum)} text-white shadow-lg`}
        >
          <div className="text-xs font-medium opacity-80">{getMomentumLabel(item.momentum)}</div>
          <div className="text-sm font-bold mt-1 truncate">{item.theme_name}</div>
          <div className="flex items-end justify-between mt-3">
            <div>
              <div className="text-2xl font-bold">{item.news_count}</div>
              <div className="text-xs opacity-80">뉴스</div>
            </div>
            <div className="text-right">
              <div className="text-lg font-bold">
                {item.momentum > 0 ? '+' : ''}{item.momentum}%
              </div>
              <div className="text-xs opacity-80">WoW</div>
            </div>
          </div>
          {item.top_stocks.length > 0 && (
            <div className="mt-2 pt-2 border-t border-white/20 text-xs opacity-80 truncate">
              {item.top_stocks.slice(0, 3).map(s => s.name).join(', ')}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
