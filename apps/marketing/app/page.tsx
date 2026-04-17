import { LINKS } from '@/lib/config'
import {
  FlaskConical, Activity, BellRing, Smartphone, Network, ShieldCheck,
  ArrowRight, Play, Calendar, ChevronRight
} from 'lucide-react'

function NavBar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 lg:px-12 py-4 bg-[rgba(5,5,8,0.8)] backdrop-blur-xl border-b border-[var(--border)]">
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-white shadow-[0_0_0_1px_rgba(255,255,255,0.08),0_2px_10px_rgba(0,0,0,0.18)]">
          <img
            alt="airbc icon"
            className="h-full w-full object-cover"
            src="/favicon.svg"
          />
        </div>
        <span className="text-lg font-bold tracking-tight text-white">airbc</span>
      </div>
      <div className="flex items-center gap-3">
        <a href={LINKS.SIGN_IN} className="text-sm text-white/70 hover:text-white transition-colors">Sign in</a>
        <a href={LINKS.SIGN_UP} className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]">
          Get started <ArrowRight className="h-3.5 w-3.5" />
        </a>
      </div>
    </nav>
  )
}

function HeroSection() {
  return (
    <section className="relative min-h-screen flex flex-col items-center justify-center text-center px-6 pt-24 pb-20 overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(196,30,48,0.08)_0%,transparent_70%)]" />
      <div className="relative z-10 max-w-4xl mx-auto space-y-8">
        <div className="inline-flex items-center gap-2 rounded-full border border-[var(--border-accent)] bg-[var(--accent-soft)] px-4 py-1.5 text-xs font-medium text-[var(--accent-hover)]">
          <Activity className="h-3 w-3" /> AI-Powered Blood Bag Conservation
        </div>
        <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight leading-[1.08]">
          Monitor <span style={{ color: 'var(--accent)' }}>Blood</span> Bag<br />
          Conservation in Real Time
        </h1>
        <p className="text-lg sm:text-xl text-[var(--text-muted)] max-w-2xl mx-auto leading-relaxed">
          Track glucose depletion, ATP decline, and metabolic drift throughout storage.
          Detect quality changes before they become critical
          with RBC metabolic modeling and AI-assisted alerting.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-2">
          <a href={LINKS.SIGN_UP} className="inline-flex items-center gap-2 rounded-xl bg-[var(--accent)] px-7 py-3.5 text-base font-semibold text-white transition-all hover:bg-[var(--accent-hover)] hover:shadow-[0_0_40px_rgba(196,30,48,0.3)]">
            Create free account <ArrowRight className="h-4 w-4" />
          </a>
          <a href={LINKS.BOOK_DEMO} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg-elevated)] px-7 py-3.5 text-base font-medium text-[var(--text-main)] transition-colors hover:bg-[var(--bg-card)]">
            <Calendar className="h-4 w-4" /> Schedule a demo
          </a>
        </div>
      </div>
      <div className="relative z-10 mt-16 w-full max-w-5xl mx-auto">
        <HeroMockup />
      </div>
    </section>
  )
}

function HeroMockup() {
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--bg-elevated)] p-1 shadow-[0_30px_80px_rgba(0,0,0,0.5)]">
      <div className="rounded-xl bg-[var(--bg-card)] p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-3 w-3 rounded-full bg-[var(--accent)] animate-pulse" />
            <span className="text-sm font-medium text-[var(--text-main)]">Unit #RBC-2026-0342</span>
            <span className="text-xs text-[var(--text-dim)] border border-[var(--border)] rounded px-2 py-0.5">Day 18 / 42</span>
            <span className="text-xs text-[var(--text-dim)] border border-[var(--border)] rounded px-2 py-0.5">CPD-SAGM</span>
            <span className="text-xs text-[var(--text-dim)] border border-[var(--border)] rounded px-2 py-0.5">4Â°C</span>
          </div>
          <span className="text-xs font-medium text-amber-400 border border-amber-400/20 rounded-full px-2.5 py-0.5 bg-amber-400/10">Attention needed</span>
        </div>
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: 'Glucose', value: '2.8 mM', trend: 'â†“ 44%', color: 'text-red-400' },
            { label: 'ATP', value: '1.2 mM', trend: 'â†“ 28%', color: 'text-amber-400' },
            { label: 'Lactate', value: '18.4 mM', trend: 'â†‘ 312%', color: 'text-red-400' },
            { label: '2,3-BPG', value: '2.1 mM', trend: 'â†“ 53%', color: 'text-amber-400' },
          ].map((m) => (
            <div key={m.label} className="rounded-lg bg-[rgba(255,255,255,0.02)] border border-[var(--border)] p-3">
              <p className="text-[10px] text-[var(--text-dim)] uppercase tracking-wider">{m.label}</p>
              <p className="text-lg font-bold text-[var(--text-main)] mt-1">{m.value}</p>
              <p className={`text-xs font-medium mt-0.5 ${m.color}`}>{m.trend}</p>
            </div>
          ))}
        </div>
        <div className="flex items-start gap-3 rounded-lg bg-[var(--accent-soft)] border border-[var(--border-accent)] p-3 animate-pulse" style={{ boxShadow: '0 0 15px rgba(196,30,48,0.15), inset 0 0 15px rgba(196,30,48,0.05)' }}>
          <BellRing className="h-4 w-4 text-[var(--accent)] shrink-0 mt-0.5" style={{ filter: 'drop-shadow(0 0 6px rgba(196,30,48,0.6))' }} />
          <div>
            <p className="text-xs font-medium text-[var(--text-main)]">RoBoCop AI Alert</p>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">Glucose depletion approaching critical threshold. ATP decline rate exceeds baseline by 1.8Ã—. Consider reviewing storage conditions for this unit.</p>
          </div>
        </div>
        <div className="h-32 rounded-lg bg-[rgba(255,255,255,0.015)] border border-[var(--border)] flex items-end p-4 gap-1">
          {[28, 35, 42, 50, 55, 48, 62, 70, 65, 72, 78, 85, 80, 88, 92, 87, 95, 90, 82, 75, 68, 60, 52, 45].map((h, i) => (
            <div key={i} className="flex-1 rounded-sm transition-all" style={{ height: `${h}%`, background: h > 75 ? 'var(--accent)' : 'rgba(255,255,255,0.08)' }} />
          ))}
        </div>
      </div>
    </div>
  )
}

function UseCaseSection() {
  return (
    <section className="px-6 lg:px-12 py-28 max-w-6xl mx-auto">
      <div className="text-center space-y-4 mb-16">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--accent)]">How it works</p>
        <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">Follow every blood bag from storage to decision</h2>
        <p className="text-[var(--text-muted)] max-w-2xl mx-auto">A researcher stores a blood unit. airbc continuously tracks metabolic state, surfaces AI-generated insights, and enables remote follow-up from any device.</p>
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {[
          { step: '01', title: 'Quantify', desc: 'Run extracellular metabolite analysis on your stored blood units to establish baseline concentrations and generate the input data the platform needs.', icon: Activity },
          { step: '02', title: 'Store & Simulate', desc: 'Configure a storage scenario and run mechanistic simulations to predict how metabolite concentrations evolve over the full 42-day storage window.', icon: FlaskConical },
          { step: '03', title: 'Monitor & Alert', desc: 'The platform continuously tracks key indicators â€” glucose, ATP, lactate, 2,3-BPG â€” and RoBoCop AI flags meaningful shifts before they become critical.', icon: BellRing },
          { step: '04', title: 'Act & Follow Up', desc: 'Review AI summaries from the web platform or receive updates on your phone through secure messaging workflows for remote oversight.', icon: Smartphone },
        ].map((s) => {
          const Icon = s.icon
          return (
            <div key={s.step} className="rounded-2xl border border-[var(--border)] bg-[var(--bg-elevated)] p-6 space-y-4 hover:border-[var(--border-accent)] transition-colors">
              <div className="flex items-center gap-3">
                <span className="text-xs font-mono text-[var(--accent)]">{s.step}</span>
                <div className="h-px flex-1 bg-[var(--border)]" />
              </div>
              <div className="h-10 w-10 rounded-xl bg-[var(--accent-soft)] flex items-center justify-center">
                <Icon className="h-5 w-5 text-[var(--accent)]" />
              </div>
              <h3 className="text-lg font-semibold">{s.title}</h3>
              <p className="text-sm text-[var(--text-muted)] leading-relaxed">{s.desc}</p>
            </div>
          )
        })}
      </div>
    </section>
  )
}

function CapabilitiesSection() {
  return (
    <section className="px-6 lg:px-12 py-28 border-t border-[var(--border)]">
      <div className="max-w-6xl mx-auto">
        <div className="text-center space-y-4 mb-16">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--accent)]">Platform capabilities</p>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">Everything you need for RBC storage research</h2>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {[
            { title: 'Mechanistic Simulation', desc: 'Run ODE-based simulations of ~200 reactions across 8 metabolic pathways over configurable storage horizons.', icon: FlaskConical },
            { title: 'Conservation Monitoring', desc: 'Track glucose depletion, ATP decline, lactate accumulation, and redox state changes throughout storage.', icon: Activity },
            { title: 'AI-Assisted Alerts', desc: 'RoBoCop AI interprets trajectory data, surfaces quality signals, and generates actionable summaries.', icon: BellRing },
            { title: 'Pathway Interpretation', desc: 'Explore the metabolic network structure and understand how storage affects glycolysis, PPP, and nucleotide metabolism.', icon: Network },
          ].map((c) => {
            const Icon = c.icon
            return (
              <div key={c.title} className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-5 space-y-3 hover:border-[var(--border-accent)] transition-colors">
                <div className="h-9 w-9 rounded-lg bg-[var(--accent-soft)] flex items-center justify-center">
                  <Icon className="h-4 w-4 text-[var(--accent)]" />
                </div>
                <h3 className="text-sm font-semibold">{c.title}</h3>
                <p className="text-xs text-[var(--text-muted)] leading-relaxed">{c.desc}</p>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}

function AIRemoteSection() {
  return (
    <section className="px-6 lg:px-12 py-28 border-t border-[var(--border)]">
      <div className="max-w-5xl mx-auto grid lg:grid-cols-2 gap-16 items-center">
        <div className="space-y-6">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--accent)]">AI + Remote supervision</p>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight leading-tight">
            Monitor from anywhere.<br />
            <span style={{ color: 'var(--accent)' }}>AI keeps you informed.</span>
          </h2>
          <p className="text-[var(--text-muted)] leading-relaxed">
            RoBoCop AI monitors your stored units in real time, generates quality summaries when metabolic indicators shift, and delivers actionable alerts â€” to the web dashboard or through planned secure messaging workflows on your phone.
          </p>
          <div className="space-y-3 pt-2">
            {[
              'AI-generated quality summaries when key metabolites shift',
              'Automated alerts on glucose depletion, ATP decline, and lactate rise',
              'Planned mobile follow-up via secure messaging (Telegram, WhatsApp)',
              'Remote oversight without being tied to the lab desktop',
            ].map((item) => (
              <div key={item} className="flex items-start gap-3">
                <ShieldCheck className="h-4 w-4 text-[var(--accent)] shrink-0 mt-0.5" />
                <span className="text-sm text-[var(--text-muted)]">{item}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--bg-elevated)] p-6 space-y-4">
          <div className="flex items-center gap-2 text-xs text-[var(--text-dim)]">
            <Smartphone className="h-3.5 w-3.5" /> Secure messaging preview
          </div>
          <div className="space-y-3">
            <div className="flex justify-start">
              <div className="max-w-[85%] rounded-xl px-4 py-2.5 text-xs leading-relaxed bg-[rgba(255,255,255,0.04)] border border-[var(--border)] text-[var(--text-muted)]">
                <p className="font-semibold text-[var(--text-main)] mb-1">RoBoCop</p>
                <p>Unit RBC-0342 alert: glucose dropped to 2.1 mM (day 21). ATP at 0.9 mM. Recommend reviewing storage conditions.</p>
                <p className="text-[10px] mt-1 opacity-50 text-right">14:23</p>
              </div>
            </div>
            <div className="flex justify-end">
              <div className="max-w-[85%] rounded-xl px-4 py-2.5 text-xs leading-relaxed bg-[var(--accent)] text-white">
                <p>Show me the full trajectory comparison for this unit.</p>
                <p className="text-[10px] mt-1 opacity-50 text-right">14:25</p>
              </div>
            </div>
            <div className="flex justify-start">
              <div className="max-w-[90%] rounded-xl px-4 py-2.5 text-xs leading-relaxed bg-[rgba(255,255,255,0.04)] border border-[var(--border)] text-[var(--text-muted)]">
                <p className="font-semibold text-[var(--text-main)] mb-1">RoBoCop</p>
                <p className="mb-2">Here is the 21-day metabolites monitoring. Lactate accumulation confirms increased glycolytic stress. Full report available on the dashboard.</p>
                <div className="rounded-lg bg-[rgba(0,0,0,0.3)] border border-[var(--border)] p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[9px] font-medium text-[var(--text-dim)] uppercase tracking-wider">21-Day Metabolite Monitoring</span>
                  </div>
                  <svg viewBox="0 0 220 130" className="w-full" style={{ fontFamily: 'var(--font-sans)' }}>
                    <line x1="28" y1="10" x2="28" y2="95" stroke="rgba(255,255,255,0.06)" strokeWidth="0.5" />
                    <line x1="28" y1="95" x2="195" y2="95" stroke="rgba(255,255,255,0.06)" strokeWidth="0.5" />
                    <text x="42" y="108" textAnchor="middle" fontSize="7" fill="rgba(255,255,255,0.3)">D0</text>
                    <text x="97" y="108" textAnchor="middle" fontSize="7" fill="rgba(255,255,255,0.3)">D7</text>
                    <text x="152" y="108" textAnchor="middle" fontSize="7" fill="rgba(255,255,255,0.3)">D14</text>
                    <text x="195" y="108" textAnchor="middle" fontSize="7" fill="rgba(255,255,255,0.3)">D21</text>
                    <text x="10" y="22" fontSize="6" fill="rgba(255,255,255,0.25)">mM</text>
                    <polyline points="42,20 75,22 110,26 140,32 165,40 180,48 195,55" fill="none" stroke="#ef4444" strokeWidth="1.5" strokeLinejoin="round" />
                    <text x="195" y="53" textAnchor="start" dx="4" fontSize="7" fontWeight="600" fill="#ef4444">GLC â†“</text>
                    <polyline points="42,80 75,74 110,62 140,48 165,35 180,26 195,18" fill="none" stroke="#3b82f6" strokeWidth="1.5" strokeLinejoin="round" />
                    <text x="195" y="16" textAnchor="start" dx="4" fontSize="7" fontWeight="600" fill="#3b82f6">LAC â†‘</text>
                    <polyline points="42,38 75,40 110,44 140,50 165,58 180,64 195,70" fill="none" stroke="#f59e0b" strokeWidth="1.5" strokeLinejoin="round" />
                    <text x="195" y="68" textAnchor="start" dx="4" fontSize="7" fontWeight="600" fill="#f59e0b">ATP â†“</text>
                    <polyline points="42,50 75,53 110,58 140,65 165,72 180,78 195,84" fill="none" stroke="#a855f7" strokeWidth="1.5" strokeLinejoin="round" strokeDasharray="3,2" />
                    <text x="195" y="82" textAnchor="start" dx="4" fontSize="7" fontWeight="600" fill="#a855f7">BPG â†“</text>
                  </svg>
                </div>
                <p className="text-[10px] mt-2 opacity-50 text-right">14:25</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

function WhyItMattersSection() {
  return (
    <section className="px-6 lg:px-12 py-28 border-t border-[var(--border)]">
      <div className="max-w-4xl mx-auto text-center space-y-6">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--accent)]">Why it matters</p>
        <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">Grounded in mechanistic RBC research</h2>
          <p className="text-[var(--text-muted)] max-w-2xl mx-auto leading-relaxed">
          Built on the Bordbar et al. (2015) whole-cell kinetic reconstruction of red blood cell metabolism.
          airbc models the storage lesion â€” the progressive metabolic deterioration that affects transfusion quality â€” and helps researchers detect meaningful shifts before they compromise the stored unit.
        </p>
        <div className="grid sm:grid-cols-3 gap-8 pt-8">
          {[
            { value: '113', label: 'Metabolites tracked' },
            { value: '42', label: 'Day storage horizon' },
            { value: '~200', label: 'Reactions modeled' },
          ].map((s) => (
            <div key={s.label}>
              <p className="text-4xl font-bold" style={{ color: 'var(--accent)' }}>{s.value}</p>
              <p className="text-sm text-[var(--text-muted)] mt-1">{s.label}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function FinalCTASection() {
  return (
    <section className="px-6 lg:px-12 py-28 border-t border-[var(--border)]">
      <div className="max-w-3xl mx-auto text-center space-y-8">
        <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">Start monitoring your stored blood units</h2>
          <p className="text-[var(--text-muted)] whitespace-nowrap">Join researchers and blood banking teams using airbc to follow RBC conservation with AI-assisted precision.</p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <a href={LINKS.SIGN_UP} className="inline-flex items-center gap-2 rounded-xl bg-[var(--accent)] px-7 py-3.5 text-base font-semibold text-white transition-all hover:bg-[var(--accent-hover)] hover:shadow-[0_0_40px_rgba(196,30,48,0.3)]">
            Create free account <ArrowRight className="h-4 w-4" />
          </a>
          <a href={LINKS.SIGN_IN} className="inline-flex items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg-elevated)] px-7 py-3.5 text-base font-medium transition-colors hover:bg-[var(--bg-card)]">
            Sign in <ChevronRight className="h-4 w-4" />
          </a>
          <a href={LINKS.BOOK_DEMO} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 text-sm text-[var(--text-muted)] hover:text-[var(--text-main)] transition-colors">
            <Calendar className="h-4 w-4" /> Book a demo
          </a>
        </div>
      </div>
      <footer className="mt-24 pt-8 border-t border-[var(--border)] text-center">
        <p className="text-xs text-[var(--text-dim)]">
          airbc &middot; Polytechnique Montreal &middot; Jolicoeur Lab &mdash; 2026
        </p>
      </footer>
    </section>
  )
}

export default function HomePage() {
  return (
    <>
      <NavBar />
      <HeroSection />
      <UseCaseSection />
      <CapabilitiesSection />
      <AIRemoteSection />
      <WhyItMattersSection />
      <FinalCTASection />
    </>
  )
}
