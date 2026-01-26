import { create } from 'zustand'
import type { Idea, IdeaWithPositions, DashboardData } from '../types/idea'
import { ideaApi, dashboardApi } from '../services/api'

interface IdeaState {
  ideas: Idea[]
  currentIdea: IdeaWithPositions | null
  dashboard: DashboardData | null
  loading: boolean
  error: string | null

  fetchIdeas: (params?: { status?: string; type?: string }) => Promise<void>
  fetchIdea: (id: string) => Promise<void>
  fetchDashboard: () => Promise<void>
  clearError: () => void
}

export const useIdeaStore = create<IdeaState>((set) => ({
  ideas: [],
  currentIdea: null,
  dashboard: null,
  loading: false,
  error: null,

  fetchIdeas: async (params) => {
    set({ loading: true, error: null })
    try {
      const ideas = await ideaApi.list(params)
      set({ ideas, loading: false })
    } catch (err) {
      set({ error: '아이디어 목록을 불러오는데 실패했습니다.', loading: false })
    }
  },

  fetchIdea: async (id) => {
    set({ loading: true, error: null })
    try {
      const idea = await ideaApi.get(id)
      set({ currentIdea: idea, loading: false })
    } catch (err) {
      set({ error: '아이디어를 불러오는데 실패했습니다.', loading: false })
    }
  },

  fetchDashboard: async () => {
    set({ loading: true, error: null })
    try {
      const dashboard = await dashboardApi.get()
      set({ dashboard, loading: false })
    } catch (err) {
      set({ error: '대시보드 데이터를 불러오는데 실패했습니다.', loading: false })
    }
  },

  clearError: () => set({ error: null }),
}))
