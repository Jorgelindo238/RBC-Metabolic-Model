'use client'

import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { Info, X } from 'lucide-react'

/**
 * Main content plus one inspector for provenance and details.
 * Side column from 1280px, bottom sheet below 1024px, inline in between. Escape closes it.
 */
export function WithInspector({ title = 'Details', defaultOpen = false, inspector, children, anchorId, open: controlledOpen, onOpenChange }: {
  title?: string
  defaultOpen?: boolean
  inspector: ReactNode
  children: ReactNode
  /** Historical section id (e.g. a former "Provenance" anchor): `#id` or `?subsection=id` opens the inspector. */
  anchorId?: string
  /** Optional controlled mode, e.g. a graph selection opening the inspector. */
  open?: boolean
  onOpenChange?: (open: boolean) => void
}) {
  const [uncontrolledOpen, setUncontrolledOpen] = useState(defaultOpen)
  const open = controlledOpen ?? uncontrolledOpen
  const setOpen = useCallback((value: boolean | ((current: boolean) => boolean)) => {
    const next = typeof value === 'function' ? value(open) : value
    if (controlledOpen === undefined) setUncontrolledOpen(next)
    onOpenChange?.(next)
  }, [controlledOpen, onOpenChange, open])

  useEffect(() => {
    if (!anchorId) return
    const sync = () => {
      const requested = new URLSearchParams(window.location.search).get('subsection')
      if (window.location.hash.slice(1) === anchorId || requested === anchorId) setOpen(true)
    }
    sync()
    window.addEventListener('hashchange', sync)
    return () => window.removeEventListener('hashchange', sync)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [anchorId])
  const inspectorId = useId()
  const triggerRef = useRef<HTMLButtonElement>(null)
  const inspectorRef = useRef<HTMLElement>(null)
  const close = useCallback(() => {
    setOpen(false)
    triggerRef.current?.focus({ preventScroll: true })
  }, [setOpen])

  useEffect(() => {
    if (!open) return
    inspectorRef.current?.focus({ preventScroll: true })
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, close])

  return (
    <div className="r-with-inspector" data-open={open} id={anchorId}>
      <div className="min-w-0">
        <div className="r-toolbar justify-end">
          <button ref={triggerRef} type="button" className="research-icon-button" aria-expanded={open}
            aria-controls={open ? inspectorId : undefined} aria-label={title} title={title}
            onClick={() => setOpen((value) => !value)}>
            <Info size={15} aria-hidden="true" />
          </button>
        </div>
        {children}
      </div>
      {open ? (
        <aside ref={inspectorRef} id={inspectorId} className="r-inspector" aria-label={title} tabIndex={-1}>
          <div className="r-toolbar justify-between">
            <h2>{title}</h2>
            <button type="button" className="research-icon-button" aria-label={`Close ${title}`} title="Close"
              onClick={close}>
              <X size={15} aria-hidden="true" />
            </button>
          </div>
          {inspector}
        </aside>
      ) : null}
    </div>
  )
}
