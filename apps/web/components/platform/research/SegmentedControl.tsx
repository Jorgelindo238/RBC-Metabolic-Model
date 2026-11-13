'use client'

import { useRef, type KeyboardEvent } from 'react'

export interface SegmentedOption<T extends string> {
  id: T
  label: string
  panelId?: string
}

/** Real view switch: exactly one view is shown. Arrow keys, Home and End move the selection. */
export function SegmentedControl<T extends string>({ label, options, value, onChange }: {
  label: string
  options: readonly SegmentedOption<T>[]
  value: T
  onChange: (id: T) => void
}) {
  const refs = useRef<Array<HTMLButtonElement | null>>([])

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const index = options.findIndex((option) => option.id === value)
    const next = event.key === 'ArrowRight' ? (index + 1) % options.length
      : event.key === 'ArrowLeft' ? (index - 1 + options.length) % options.length
        : event.key === 'Home' ? 0
          : event.key === 'End' ? options.length - 1
            : -1
    if (next < 0) return
    event.preventDefault()
    onChange(options[next].id)
    refs.current[next]?.focus()
  }

  return (
    <div className="r-segmented" role="tablist" aria-label={label} onKeyDown={onKeyDown}>
      {options.map((option, i) => (
        <button
          key={option.id}
          ref={(node) => { refs.current[i] = node }}
          type="button"
          role="tab"
          id={option.panelId ? `${option.panelId}-tab` : undefined}
          aria-selected={option.id === value}
          aria-controls={option.panelId}
          tabIndex={option.id === value ? 0 : -1}
          onClick={() => onChange(option.id)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
