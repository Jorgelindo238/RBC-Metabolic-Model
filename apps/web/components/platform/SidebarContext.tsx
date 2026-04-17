'use client'

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { PLATFORM_NAV_SECTIONS } from '../../lib/platform-navigation.ts'

const DEFAULT_SECTION_STATE = Object.freeze(
  PLATFORM_NAV_SECTIONS.reduce<Record<string, boolean>>((state, section) => {
    state[section.id] = section.id !== 'platform-direction'
    return state
  }, {})
)

interface SidebarContextShape {
  compact: boolean
  mobileOpen: boolean
  openMobile: () => void
  closeMobile: () => void
  toggleCompact: () => void
  expandSidebar: () => void
  isSectionOpen: (sectionId: string) => boolean
  toggleSection: (sectionId: string) => void
}

const SidebarContext = createContext<SidebarContextShape | null>(null)

export function SidebarProvider({ children }: { children: ReactNode }) {
  const [compact, setCompact] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [openSections, setOpenSections] = useState<Record<string, boolean>>(DEFAULT_SECTION_STATE)

  useEffect(() => {
    const syncViewportState = () => {
      if (window.innerWidth > 1180) {
        setMobileOpen(false)
      }
    }

    syncViewportState()
    window.addEventListener('resize', syncViewportState)
    return () => window.removeEventListener('resize', syncViewportState)
  }, [])

  const closeMobile = useCallback(() => setMobileOpen(false), [])
  const openMobile = useCallback(() => setMobileOpen(true), [])
  const toggleCompact = useCallback(() => setCompact(value => !value), [])
  const expandSidebar = useCallback(() => setCompact(false), [])
  const isSectionOpen = useCallback(
    (sectionId: string) => openSections[sectionId] ?? true,
    [openSections]
  )

  const toggleSection = useCallback((sectionId: string) => {
    setOpenSections(previous => ({
      ...previous,
      [sectionId]: !(previous[sectionId] ?? true),
    }))
  }, [])

  const value = useMemo(
    () => ({
      compact,
      mobileOpen,
      openMobile,
      closeMobile,
      toggleCompact,
      expandSidebar,
      isSectionOpen,
      toggleSection,
    }),
    [closeMobile, compact, expandSidebar, isSectionOpen, mobileOpen, openMobile, toggleCompact, toggleSection]
  )

  return <SidebarContext.Provider value={value}>{children}</SidebarContext.Provider>
}

export function useSidebar() {
  const context = useContext(SidebarContext)

  if (!context) {
    throw new Error('useSidebar must be used within SidebarProvider')
  }

  return context
}
