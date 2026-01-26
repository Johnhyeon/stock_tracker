import { useState, useEffect } from 'react'

type ThemeMode = 'light' | 'dark' | 'auto'

function getSystemDarkMode(): boolean {
  // 시스템 시간 기준: 18시~6시는 다크모드
  const hour = new Date().getHours()
  return hour >= 18 || hour < 6
}

export function useDarkMode() {
  const [mode, setMode] = useState<ThemeMode>(() => {
    const saved = localStorage.getItem('theme-mode')
    return (saved as ThemeMode) || 'auto'
  })

  const [isDark, setIsDark] = useState(() => {
    if (mode === 'auto') return getSystemDarkMode()
    return mode === 'dark'
  })

  useEffect(() => {
    localStorage.setItem('theme-mode', mode)

    if (mode === 'auto') {
      setIsDark(getSystemDarkMode())
      // 1분마다 시간 체크
      const interval = setInterval(() => {
        setIsDark(getSystemDarkMode())
      }, 60000)
      return () => clearInterval(interval)
    } else {
      setIsDark(mode === 'dark')
    }
  }, [mode])

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [isDark])

  const toggleMode = () => {
    setMode((prev) => {
      if (prev === 'auto') return 'light'
      if (prev === 'light') return 'dark'
      return 'auto'
    })
  }

  return { mode, isDark, setMode, toggleMode }
}
