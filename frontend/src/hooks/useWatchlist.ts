import { useEffect, useCallback } from 'react'
import { useWatchlistStore } from '../store/useWatchlistStore'

export function useWatchlist() {
  const watchedMap = useWatchlistStore(s => s.watchedMap)
  const metaMap = useWatchlistStore(s => s.metaMap)
  const groups = useWatchlistStore(s => s.groups)
  const _initialized = useWatchlistStore(s => s._initialized)
  const storeInit = useWatchlistStore(s => s.init)
  const storeToggle = useWatchlistStore(s => s.toggleWatch)

  useEffect(() => {
    storeInit()
  }, [storeInit])

  const isWatched = useCallback((code: string) => !!watchedMap[code], [watchedMap])

  const toggleWatch = useCallback(async (code: string, name?: string, groupId?: number) => {
    return storeToggle(code, name, groupId)
  }, [storeToggle])

  const getWatchlistDate = useCallback((code: string): string | undefined => {
    const meta = metaMap[code]
    if (!meta) return undefined
    return meta.created_at.split('T')[0]
  }, [metaMap])

  return {
    watchedCodes: new Set(Object.keys(watchedMap).filter(k => watchedMap[k])),
    isWatched,
    toggleWatch,
    loading: !_initialized,
    getWatchlistDate,
    groups,
  }
}
