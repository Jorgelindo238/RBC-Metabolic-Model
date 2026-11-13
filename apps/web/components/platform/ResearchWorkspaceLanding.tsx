import Link from 'next/link'
import { ArrowUpRight, Database, SlidersHorizontal, Play, ChartNoAxesCombined, Network, History } from 'lucide-react'

const GROUPS = [
  { id: 'research-map', title: 'Prepare', items: [
    { href: '/research/data-upload', title: 'Data Upload', detail: 'Files, metabolite mapping, data review', icon: Database },
    { href: '/research/parameter-calibration', title: 'Calibration', detail: 'Data contract, reference, advanced settings', icon: SlidersHorizontal },
  ] },
  { id: 'workflow-orientation', title: 'Simulate', items: [
    { href: '/research/simulation', title: 'Simulation', detail: 'Storage conditions and concentration trajectories', icon: Play },
  ] },
  { id: 'advanced-analysis', title: 'Analyse & review', items: [
    { href: '/research/flux-analysis', title: 'Flux Analysis', detail: 'Pathway fluxes and reaction rates', icon: ChartNoAxesCombined },
    { href: '/research/pathway-visualization', title: 'Pathway Map', detail: 'Network and concentration states', icon: Network },
    { href: '/research/calibration-registry', title: 'Results', detail: 'Recorded runs and evidence', icon: History },
  ] },
]

export function ResearchWorkspaceLanding() {
  return <div className="research-overview">
    {GROUPS.map((group) => <section className="research-section" id={group.id} key={group.id}>
      <h2>{group.title}</h2>
      <div className="research-tool-list">{group.items.map(({ href, title, detail, icon: Icon }) => (
        <Link key={href} href={href} className="research-tool-link">
          <Icon size={19} aria-hidden="true" /><strong>{title}</strong>
          <span className="research-muted">{detail}</span><ArrowUpRight size={16} aria-hidden="true" />
        </Link>
      ))}</div>
    </section>)}
  </div>
}
