import { clsx } from 'clsx'

interface CardProps {
  children: React.ReactNode
  className?: string
  variant?: 'default' | 'glow' | 'signal'
  compact?: boolean
  onClick?: () => void
}

export function Card({ children, className, variant = 'default', compact, onClick }: CardProps) {
  return (
    <div
      className={clsx(
        'rounded-lg border transition-all duration-200',
        'bg-white dark:bg-t-bg-card',
        variant === 'default' && 'border-gray-200 dark:border-t-border hover:border-gray-300 dark:hover:border-t-border-hover',
        variant === 'glow' && 'border-amber-200 dark:border-amber-500/20 shadow-glow-accent',
        variant === 'signal' && 'border-gray-200 dark:border-t-border',
        onClick && 'cursor-pointer hover:shadow-md dark:hover:shadow-glow-sm',
        compact && 'p-0',
        className
      )}
      onClick={onClick}
    >
      {children}
    </div>
  )
}

export function CardHeader({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={clsx('px-5 py-3.5 border-b border-gray-200 dark:border-t-border', className)}>
      {children}
    </div>
  )
}

export function CardContent({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={clsx('px-5 py-4', className)}>{children}</div>
}

export function CardFooter({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={clsx('px-5 py-3.5 border-t border-gray-200 dark:border-t-border bg-gray-50 dark:bg-t-bg-elevated rounded-b-lg', className)}>
      {children}
    </div>
  )
}
