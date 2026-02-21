import { clsx } from 'clsx'

interface BadgeProps {
  children: React.ReactNode
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'live' | 'signal'
  size?: 'sm' | 'md'
}

export default function Badge({ children, variant = 'default', size = 'sm' }: BadgeProps) {
  const variants = {
    default: 'bg-gray-100 text-gray-800 dark:bg-t-bg-elevated dark:text-t-text-secondary',
    success: 'bg-green-100 text-green-800 dark:bg-emerald-500/10 dark:text-emerald-400',
    warning: 'bg-yellow-100 text-yellow-800 dark:bg-amber-500/10 dark:text-amber-400',
    danger: 'bg-red-100 text-red-800 dark:bg-red-500/10 dark:text-red-400 dark:shadow-[0_0_6px_rgba(239,68,68,0.15)]',
    info: 'bg-blue-100 text-blue-800 dark:bg-blue-500/10 dark:text-blue-400',
    live: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-400 dark:shadow-[0_0_6px_rgba(16,185,129,0.2)]',
    signal: 'bg-amber-100 text-amber-800 dark:bg-amber-500/10 dark:text-amber-400 dark:shadow-glow-sm',
  }

  const sizes = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-sm',
  }

  return (
    <span
      className={clsx(
        'inline-flex items-center font-medium rounded-full transition-colors',
        variants[variant],
        sizes[size]
      )}
    >
      {variant === 'live' && (
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse-live mr-1.5" />
      )}
      {children}
    </span>
  )
}
