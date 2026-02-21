import { create } from 'zustand'
import type { SchedulerStatus } from '../types/data'
import { schedulerApi } from '../services/api'

interface SchedulerState {
  status: SchedulerStatus | null
  loading: boolean

  fetchStatus: () => Promise<void>
}

export const useSchedulerStore = create<SchedulerState>((set) => ({
  status: null,
  loading: false,

  fetchStatus: async () => {
    set({ loading: true })
    try {
      const status = await schedulerApi.getStatus()
      set({ status, loading: false })
    } catch {
      set({ loading: false })
    }
  },
}))
