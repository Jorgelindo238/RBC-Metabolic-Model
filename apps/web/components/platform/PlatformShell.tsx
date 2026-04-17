import { Suspense, type ReactNode } from 'react'
import { SidebarProvider } from './SidebarContext.tsx'
import { PlatformSidebar } from './PlatformSidebar.tsx'
import { PlatformHeader } from './PlatformHeader.tsx'
import { ResearchContextProvider } from '@/contexts/ResearchContextProvider'
import { ResearchDatasetProvider } from '@/contexts/ResearchDatasetProvider'
import { PlatformShellWithRoBoCop } from './PlatformShellWithRoBoCop'
import type { ProductContextShape } from './platform-shell.types'

function buildShellProductContext(productContext: ProductContextShape): ProductContextShape {
  return {
    isAuthenticated: productContext?.isAuthenticated ?? false,
    isAdmin: productContext?.isAdmin ?? false,
    contextState: productContext?.contextState ?? null,
    workspaceSelectionReason: productContext?.workspaceSelectionReason ?? null,
    workspaceSelectionRequired: productContext?.workspaceSelectionRequired ?? false,
    workspaceSelectionState: productContext?.workspaceSelectionState ?? null,
    storedWorkspacePreferenceState: productContext?.storedWorkspacePreferenceState ?? null,
    activeWorkspace: productContext?.activeWorkspace
      ? {
          id: productContext.activeWorkspace.id ?? null,
          name: productContext.activeWorkspace.name ?? null,
          slug: productContext.activeWorkspace.slug ?? null,
        }
      : null,
    availableWorkspaces: (productContext?.availableWorkspaces || []).map(option => ({
      workspaceId: option.workspaceId,
      membershipRole: option.membershipRole ?? null,
      workspace: option.workspace
        ? {
            id: option.workspace.id ?? null,
            name: option.workspace.name ?? null,
            slug: option.workspace.slug ?? null,
          }
        : null,
    })),
    researcherIdentity: productContext?.researcherIdentity
      ? {
          displayName: productContext.researcherIdentity.displayName ?? null,
          email: productContext.researcherIdentity.email ?? null,
          organizationName: productContext.researcherIdentity.organizationName ?? null,
        }
      : null,
  }
}

export function PlatformShell({
  children,
  productContext,
}: {
  children: ReactNode
  productContext: ProductContextShape
}) {
  const shellProductContext = buildShellProductContext(productContext)

  return (
    <SidebarProvider>
      <div className="platform-shell">
        <Suspense fallback={null}>
          <PlatformSidebar productContext={shellProductContext} />
        </Suspense>
        <div className="platform-content">
          <PlatformHeader productContext={shellProductContext} />
          <ResearchDatasetProvider>
            <ResearchContextProvider>
              <PlatformShellWithRoBoCop>
                {children}
              </PlatformShellWithRoBoCop>
            </ResearchContextProvider>
          </ResearchDatasetProvider>
        </div>
      </div>
    </SidebarProvider>
  )
}
