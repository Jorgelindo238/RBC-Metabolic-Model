import Link from 'next/link'
import { ArrowRight, BadgeCheck, FolderKanban } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { SidebarIcon } from './SidebarIcons'
import type { ProductContextShape } from './platform-shell.types'

function buildWorkspaceTitle(productContext: ProductContextShape) {
  if (!productContext?.isAuthenticated) {
    return 'Anonymous access'
  }

  if (productContext?.workspaceSelectionRequired) {
    return 'Choose active workspace'
  }

  return productContext?.activeWorkspace?.name || productContext?.activeWorkspace?.slug || 'Personal researcher scope'
}

function buildWorkspaceCopy(productContext: ProductContextShape) {
  switch (productContext?.workspaceSelectionReason) {
    case 'stored_preference_selected':
      return 'Recovered from your durable stored workspace preference.'
    case 'cookie_fallback_selected':
      return 'Using rollout fallback until a durable stored preference is present.'
    case 'stored_preference_invalid_single_membership_auto_selected':
      return 'Recovered safely after an outdated stored preference.'
    case 'single_membership_auto_selected':
      return 'Automatically selected because only one active membership exists.'
    default:
      return productContext?.workspaceSelectionRequired
        ? 'Select a workspace before relying on workspace-scoped visibility.'
        : 'Workspace and researcher context stay explicit in the shell.'
  }
}

export function SidebarWorkspaceCard({ compact, productContext }: { compact: boolean; productContext: ProductContextShape }) {
  if (compact) {
    return (
      <div
        className="grid place-items-center rounded-[18px] border border-[var(--color-border-soft)] bg-white px-0 py-3 shadow-sm"
        title={buildWorkspaceTitle(productContext)}
      >
        <FolderKanban className="h-4 w-4 text-[var(--color-accent-strong)]" />
      </div>
    )
  }

  return (
    <section className="grid gap-3 bg-transparent px-4 py-2">
      <div className="flex items-start gap-3">
        <div className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-[16px] bg-[var(--color-surface-soft)] text-[var(--color-text-main)]">
          <SidebarIcon icon="workspace" className="h-4 w-4" />
        </div>
        <div className="grid min-w-0 gap-1">
          <p className="m-0 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[var(--color-text-dim)]">Workspace</p>
          <h2 className="m-0 truncate text-[0.96rem] font-semibold tracking-[-0.03em] text-[var(--color-text-main)]">
            {buildWorkspaceTitle(productContext)}
          </h2>
          <div className="inline-flex w-fit items-center gap-1 rounded-full bg-[var(--color-success-soft)] px-2.5 py-1 text-[0.66rem] font-semibold uppercase tracking-[0.12em] text-[var(--color-success)]">
            <BadgeCheck className="h-3 w-3" />
            Active
          </div>
        </div>
      </div>
      <p className="m-0 text-[0.82rem] leading-6 text-[var(--color-text-muted)]">{buildWorkspaceCopy(productContext)}</p>
      {productContext?.workspaceSelectionRequired ? (
        <Button asChild className={cn('justify-self-start')}>
          <Link href="/">
            Resolve workspace
            <ArrowRight className="h-4 w-4" />
          </Link>
        </Button>
      ) : null}
    </section>
  )
}
