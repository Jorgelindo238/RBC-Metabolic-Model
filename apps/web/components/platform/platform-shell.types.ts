export type PlatformStatus = 'live' | 'preview' | 'planned'

export type NavIconName =
  | 'overview'
  | 'calibration'
  | 'simulation'
  | 'data'
  | 'flux'
  | 'atlas'
  | 'robocop'
  | 'prompts'
  | 'tools'
  | 'account'
  | 'settings'
  | 'billing'
  | 'workspace'
  | 'search'

export interface WorkspaceSummary {
  id?: string | null
  name?: string | null
  slug?: string | null
}

export interface WorkspaceOption {
  workspaceId: string
  membershipRole?: string | null
  workspace?: WorkspaceSummary | null
}

export interface ResearcherIdentity {
  displayName?: string | null
  email?: string | null
  organizationName?: string | null
}

export interface ProductContextShape {
  isAuthenticated?: boolean
  isAdmin?: boolean
  contextState?: string | null
  workspaceSelectionReason?: string | null
  workspaceSelectionRequired?: boolean
  workspaceSelectionState?: string | null
  storedWorkspacePreferenceState?: string | null
  activeWorkspace?: WorkspaceSummary | null
  availableWorkspaces?: WorkspaceOption[] | null
  researcherIdentity?: ResearcherIdentity | null
}

export interface PlatformNavSubsection {
  id: string
  title: string
  description: string
}

export interface PlatformNavItem {
  id: string
  title: string
  href: string
  status: PlatformStatus
  description: string
  icon: NavIconName
  badgeText?: string
  badgeCount?: number
  children?: readonly PlatformNavSubsection[]
}

export interface PlatformNavSection {
  id: string
  label: string
  eyebrow?: string
  collapsible?: boolean
  items: PlatformNavItem[]
}

export interface PlatformModuleCard {
  title: string
  status: PlatformStatus
  description: string
  eyebrow: string
  icon: NavIconName
  href?: string
}

export interface SidebarSupportLink {
  label: string
  href?: string
  external?: boolean
}

export interface SidebarSupportSection {
  id: string
  eyebrow: string
  title: string
  description?: string
  tone?: 'default' | 'success'
  bullets?: readonly string[]
  links?: readonly SidebarSupportLink[]
}

export interface SidebarAccountAction {
  title: string
  href: string
  icon: Extract<NavIconName, 'account' | 'settings' | 'billing'>
  tone?: 'default' | 'danger'
  badgeText?: string
}
