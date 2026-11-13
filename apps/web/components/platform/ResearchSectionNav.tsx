'use client'

import { useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import type { PlatformNavSubsection } from './platform-shell.types'

/**
 * Jump links for long Research pages. With `hidden`, nothing is rendered but historical
 * `?subsection=` / `#id` links still open and scroll to their target (pages with their own structure).
 */
export function ResearchSectionNav({ sections, hidden = false }: { sections: readonly PlatformNavSubsection[]; hidden?: boolean }) {
  const [active, setActive] = useState(sections[0]?.id)
  const requested = useSearchParams().get('subsection')

  useEffect(() => {
    const aliases: Record<string, string> = {
      'target-scope': 'data-verification', 'parameter-scope': 'legacy-calibration',
      'benchmark-review': 'reference-profile', 'solver-controls': 'scenario-setup',
    }
    const id = requested ? aliases[requested] ?? requested : null
    if (!id || !sections.some((section) => section.id === id)) return
    const target = document.getElementById(id)
    if (target instanceof HTMLDetailsElement) target.open = true
    target?.scrollIntoView()
    setActive(id)
  }, [requested, sections])

  useEffect(() => {
    const syncHash = () => {
      const id = window.location.hash.slice(1)
      if (sections.some((section) => section.id === id)) setActive(id)
    }
    syncHash()
    window.addEventListener('hashchange', syncHash)
    return () => window.removeEventListener('hashchange', syncHash)
  }, [sections])

  if (hidden) return null

  return (
    <nav className="research-section-nav" aria-label="Page sections">
      {sections.map((section) => (
        // Jump links: no aria-current, because every section stays on the page (no tab is "active").
        <a key={section.id} href={`#${section.id}`} data-last-jump={active === section.id ? 'true' : undefined}
          onClick={() => {
            setActive(section.id)
            const target = document.getElementById(section.id)
            if (target instanceof HTMLDetailsElement) target.open = true
          }}>
          {section.title}
        </a>
      ))}
    </nav>
  )
}
