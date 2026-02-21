import { create } from 'zustand'
import { watchlistApi } from '../services/api'
import type { WatchlistGroup } from '../services/api'

interface WatchlistMeta {
  created_at: string
  memo: string | null
  group_id: number | null
}

interface WatchlistStoreState {
  watchedMap: Record<string, boolean>
  metaMap: Record<string, WatchlistMeta>
  groups: WatchlistGroup[]
  _initialized: boolean
  _groupsLoaded: boolean

  init: () => Promise<void>
  loadGroups: () => Promise<void>
  refreshGroups: () => Promise<void>
  refreshAll: () => Promise<void>
  toggleWatch: (code: string, name?: string, groupId?: number) => Promise<boolean>
}

export const useWatchlistStore = create<WatchlistStoreState>((set, get) => ({
  watchedMap: {},
  metaMap: {},
  groups: [],
  _initialized: false,
  _groupsLoaded: false,

  init: async () => {
    if (get()._initialized) return
    set({ _initialized: true })
    try {
      const items = await watchlistApi.getItems()
      const watchedMap: Record<string, boolean> = {}
      const metaMap: Record<string, WatchlistMeta> = {}
      for (const item of items) {
        watchedMap[item.stock_code] = true
        metaMap[item.stock_code] = {
          created_at: item.created_at,
          memo: item.memo,
          group_id: item.group_id,
        }
      }
      set({ watchedMap, metaMap })
    } catch { /* 조용히 실패 */ }
    // 그룹도 함께 로드
    get().loadGroups()
  },

  loadGroups: async () => {
    if (get()._groupsLoaded) return
    set({ _groupsLoaded: true })
    try {
      const groups = await watchlistApi.getGroups()
      set({ groups })
    } catch { /* 조용히 실패 */ }
  },

  refreshGroups: async () => {
    try {
      const groups = await watchlistApi.getGroups()
      set({ groups, _groupsLoaded: true })
    } catch { /* 조용히 실패 */ }
  },

  refreshAll: async () => {
    try {
      const [items, groups] = await Promise.all([
        watchlistApi.getItems(),
        watchlistApi.getGroups(),
      ])
      const watchedMap: Record<string, boolean> = {}
      const metaMap: Record<string, WatchlistMeta> = {}
      for (const item of items) {
        watchedMap[item.stock_code] = true
        metaMap[item.stock_code] = {
          created_at: item.created_at,
          memo: item.memo,
          group_id: item.group_id,
        }
      }
      set({ watchedMap, metaMap, groups, _initialized: true, _groupsLoaded: true })
    } catch { /* 조용히 실패 */ }
  },

  toggleWatch: async (code, name, groupId) => {
    const wasWatched = !!get().watchedMap[code]
    // 낙관적 업데이트
    set(s => ({
      watchedMap: { ...s.watchedMap, [code]: !wasWatched },
    }))

    try {
      const result = await watchlistApi.toggle(code, name, groupId)
      set(s => ({
        watchedMap: { ...s.watchedMap, [code]: result.is_watched },
      }))
      return result.is_watched
    } catch {
      // 롤백
      set(s => ({
        watchedMap: { ...s.watchedMap, [code]: wasWatched },
      }))
      return wasWatched
    }
  },
}))
