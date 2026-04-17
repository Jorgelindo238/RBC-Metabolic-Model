import { useEffect, useRef } from 'react'
import { Search, X } from 'lucide-react'
import { cn } from '@/lib/utils'

interface SidebarSearchProps {
  compact: boolean
  onAutoFocusHandled?: () => void
  onExpandSearch: () => void
  onQueryChange: (value: string) => void
  query: string
  shouldAutoFocus?: boolean
}

export function SidebarSearch({
  compact,
  onAutoFocusHandled,
  onExpandSearch,
  onQueryChange,
  query,
  shouldAutoFocus = false,
}: SidebarSearchProps) {
  const inputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    if (!compact && shouldAutoFocus) {
      inputRef.current?.focus()
      onAutoFocusHandled?.()
    }
  }, [compact, onAutoFocusHandled, shouldAutoFocus])

  if (compact) {
    return (
      <button
        aria-label="Expand sidebar and search modules"
        className="inline-flex h-10 w-full items-center justify-center rounded-lg border border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.04)] text-[#6b7280] transition-colors hover:bg-[rgba(255,255,255,0.08)] hover:text-[#9ca3af]"
        onClick={onExpandSearch}
        title="Search"
        type="button"
      >
        <Search className="h-4 w-4" />
      </button>
    )
  }

  return (
    <div className="flex items-center gap-2.5 rounded-lg border border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.04)] px-3 py-2 transition-colors focus-within:border-[rgba(214,40,57,0.3)] focus-within:bg-[rgba(255,255,255,0.06)]">
      <Search className="h-4 w-4 shrink-0 text-[#6b7280]" />
      <input
        aria-label="Search platform modules"
        className="w-full min-w-0 border-0 bg-transparent text-sm text-[#e2e5ea] outline-0 placeholder:text-[#4b5563]"
        onChange={event => onQueryChange(event.target.value)}
        placeholder="Search..."
        ref={inputRef}
        type="search"
        value={query}
      />
      {query ? (
        <button
          className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded text-[#6b7280] transition-colors hover:text-[#e2e5ea]"
          onClick={() => onQueryChange('')}
          type="button"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      ) : (
        <kbd className="hidden sm:inline-flex shrink-0 items-center rounded border border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.04)] px-1.5 py-0.5 text-[0.6rem] text-[#4b5563]">
          ⌘K
        </kbd>
      )}
    </div>
  )
}
