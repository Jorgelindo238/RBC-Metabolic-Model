import {
  LayoutDashboard,
  Target,
  FlaskConical,
  Database,
  BarChart3,
  Map,
  Bot,
  FileText,
  Wrench,
  User,
  Settings,
  CreditCard,
  Briefcase,
  Search,
  Circle,
} from 'lucide-react'
import type { NavIconName } from './platform-shell.types'

const ICON_MAP: Record<NavIconName, typeof Circle> = {
  overview: LayoutDashboard,
  calibration: Target,
  simulation: FlaskConical,
  data: Database,
  flux: BarChart3,
  atlas: Map,
  robocop: Bot,
  prompts: FileText,
  tools: Wrench,
  account: User,
  settings: Settings,
  billing: CreditCard,
  workspace: Briefcase,
  search: Search,
}

export function SidebarIcon({ icon, className }: { icon: NavIconName; className?: string }) {
  const Icon = ICON_MAP[icon] || Circle
  return <Icon className={className} />
}
