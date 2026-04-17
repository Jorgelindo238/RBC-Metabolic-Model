'use client'

import { createContext, useCallback, useContext, useLayoutEffect, useMemo, useState, type ReactNode } from 'react'
import type { ActiveResearchDataset, ResearchDataMode, ResearchDatasetSummary } from '@/types/research-dataset'
import type { ActiveResearchCalibration } from '@/lib/research-calibration'
import {
  persistResearchDataset,
  readPersistedResearchDataset,
  subscribeToResearchDatasetChanges,
  summarizeResearchDataset,
} from '@/lib/research-dataset'
import {
  persistResearchCalibration,
  readPersistedResearchCalibration,
  subscribeToResearchCalibrationChanges,
} from '@/lib/research-calibration'

interface ResearchDatasetContextValue {
  activeDataset: ActiveResearchDataset | null
  activeDatasetSummary: ResearchDatasetSummary
  researchDataMode: ResearchDataMode
  activeCalibration: ActiveResearchCalibration | null
  activateCustomDataset: (dataset: ActiveResearchDataset) => void
  clearActiveDataset: () => void
  activateCalibration: (calibration: ActiveResearchCalibration) => void
  clearActiveCalibration: () => void
}

const ResearchDatasetContext = createContext<ResearchDatasetContextValue | undefined>(undefined)

export function ResearchDatasetProvider({ children }: { children: ReactNode }) {
  const [activeDataset, setActiveDataset] = useState<ActiveResearchDataset | null>(null)
  const [activeCalibration, setActiveCalibration] = useState<ActiveResearchCalibration | null>(null)

  useLayoutEffect(() => {
    const syncResearchState = () => {
      setActiveDataset(readPersistedResearchDataset())
      setActiveCalibration(readPersistedResearchCalibration())
    }

    syncResearchState()

    const unsubscribeDataset = subscribeToResearchDatasetChanges(syncResearchState)
    const unsubscribeCalibration = subscribeToResearchCalibrationChanges(syncResearchState)

    return () => {
      unsubscribeDataset()
      unsubscribeCalibration()
    }
  }, [])

  const activateCustomDataset = useCallback((dataset: ActiveResearchDataset) => {
    persistResearchDataset(dataset)
  }, [])

  const clearActiveDataset = useCallback(() => {
    persistResearchDataset(null)
  }, [])

  const activateCalibration = useCallback((calibration: ActiveResearchCalibration) => {
    persistResearchCalibration(calibration)
  }, [])

  const clearActiveCalibration = useCallback(() => {
    persistResearchCalibration(null)
  }, [])

  const value = useMemo<ResearchDatasetContextValue>(() => {
    return {
      activeDataset,
      activeDatasetSummary: summarizeResearchDataset(activeDataset),
      researchDataMode: activeDataset ? 'custom_user_data_mode' : 'default_bordbar_mode',
      activeCalibration,
      activateCustomDataset,
      clearActiveDataset,
      activateCalibration,
      clearActiveCalibration,
    }
  }, [activeCalibration, activeDataset, activateCalibration, activateCustomDataset, clearActiveCalibration, clearActiveDataset])

  return <ResearchDatasetContext.Provider value={value}>{children}</ResearchDatasetContext.Provider>
}

export function useResearchDataset() {
  const value = useContext(ResearchDatasetContext)
  if (!value) {
    throw new Error('useResearchDataset must be used within ResearchDatasetProvider')
  }
  return value
}
