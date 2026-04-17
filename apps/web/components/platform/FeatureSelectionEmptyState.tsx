import Link from 'next/link'
import { ArrowRight, LayoutPanelTop } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { buildPlatformFeatureHref } from '@/lib/platform-navigation.ts'

export function FeatureSelectionEmptyState() {
  return (
    <section className="panel feature-selection-empty">
      <p className="eyebrow">Selection-driven workspace</p>
      <h1 className="page-title">Choose a feature from the sidebar</h1>
      <p className="page-copy">
        The sidebar is now the single feature catalog. Select a main feature or one of its nested subsections to open the
        focused workspace view here.
      </p>
      <div className="mt-6 flex flex-wrap gap-3">
        <Button asChild>
          <Link href={buildPlatformFeatureHref('home')}>
            <LayoutPanelTop className="size-4" />
            Open workspace home
          </Link>
        </Button>
        <Button asChild variant="secondary">
          <Link href={buildPlatformFeatureHref('calibration-registry')}>
            Review calibration registry
            <ArrowRight className="size-4" />
          </Link>
        </Button>
      </div>
      <div className="mt-6 rounded-[var(--radius)] border border-[var(--color-border-soft)] bg-[var(--color-surface-soft)] px-4 py-3 text-sm text-[var(--color-text-muted)] shadow-[var(--shadow-soft)]">
        Tailwind, shadcn/ui, and RoBoCop-owned design tokens are now wired into the Next.js platform foundation without
        changing the current Supabase SSR shell boundaries.
      </div>
    </section>
  )
}
