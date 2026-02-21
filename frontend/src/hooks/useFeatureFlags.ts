import { useState, useEffect } from 'react'
import { featuresApi } from '../services/api'

export interface FeatureFlags {
  telegram: boolean
  expert: boolean
}

const defaultFlags: FeatureFlags = { telegram: true, expert: true }

let cachedFlags: FeatureFlags | null = null
let fetchPromise: Promise<FeatureFlags> | null = null
let listeners: Set<(f: FeatureFlags) => void> = new Set()

function fetchFlags(): Promise<FeatureFlags> {
  if (cachedFlags) return Promise.resolve(cachedFlags)
  if (!fetchPromise) {
    fetchPromise = featuresApi.get()
      .then(flags => { cachedFlags = flags; return flags })
      .catch(() => defaultFlags)
  }
  return fetchPromise
}

function notifyListeners(flags: FeatureFlags) {
  listeners.forEach(fn => fn(flags))
}

export async function toggleFeatureFlag(key: keyof FeatureFlags, value: boolean): Promise<FeatureFlags> {
  const flags = await featuresApi.toggle({ [key]: value })
  cachedFlags = flags
  fetchPromise = null
  notifyListeners(flags)
  return flags
}

export function useFeatureFlags(): FeatureFlags {
  const [flags, setFlags] = useState<FeatureFlags>(cachedFlags || defaultFlags)

  useEffect(() => {
    fetchFlags().then(setFlags)
    listeners.add(setFlags)
    return () => { listeners.delete(setFlags) }
  }, [])

  return flags
}
