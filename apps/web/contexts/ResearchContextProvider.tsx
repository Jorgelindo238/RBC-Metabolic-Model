'use client'

import { createContext, useContext, ReactNode, useState } from 'react'
import type { ResearchContext } from '@/types/research-context'

interface ResearchContextValue {
  context: ResearchContext | null
  setContext: (context: ResearchContext | null) => void
}

const ResearchContextContext = createContext<ResearchContextValue | undefined>(undefined)

export function ResearchContextProvider({ children }: { children: ReactNode }) {
  const [context, setContext] = useState<ResearchContext | null>(null)

  return (
    <ResearchContextContext.Provider value={{ context, setContext }}>
      {children}
    </ResearchContextContext.Provider>
  )
}

export function useResearchContext() {
  const value = useContext(ResearchContextContext)
  if (!value) {
    throw new Error('useResearchContext must be used within ResearchContextProvider')
  }
  return value
}
