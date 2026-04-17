import type {
  PlatformModuleCard,
  PlatformNavItem,
  PlatformNavSection,
  SidebarAccountAction,
  SidebarSupportSection,
} from '../components/platform/platform-shell.types'

const FEATURE_PATHS: Readonly<Record<string, string>> = Object.freeze({
  home: '/',
  'home-robocop': '/robocop',
  'research-overview': '/research',
  'simulation-workspace': '/research/simulation',
  'data-upload': '/research/data-upload',
  'flux-analysis': '/research/flux-analysis',
  'pathway-visualization': '/research/pathway-visualization',
  'parameter-calibration': '/research/parameter-calibration',
  'calibration-registry': '/research/calibration-registry',
  'monitoring-overview': '/monitoring',
  'monitoring-robocop': '/monitoring/robocop',
  'bag-repo': '/monitoring/bag-repo',
  'quality-forecast': '/monitoring/quality-forecast',
  alerts: '/monitoring/alerts',
})

const FEATURE_ID_ALIASES: Readonly<Record<string, string>> = Object.freeze({
  'research-utilities': 'research-overview',
  'robocop-sessions': 'home-robocop',
})

export function normalizePlatformFeatureId(featureId?: string | null) {
  if (!featureId) {
    return null
  }

  return FEATURE_ID_ALIASES[featureId] ?? featureId
}

export function getPlatformWorkspaceLabel(featureId?: string | null) {
  const normalizedFeatureId = normalizePlatformFeatureId(featureId)

  if (!normalizedFeatureId) {
    return 'Workspace'
  }

  if (normalizedFeatureId === 'home') {
    return 'Home'
  }

  if (normalizedFeatureId === 'home-robocop') {
    return 'RoBoCop'
  }

  const feature = getPlatformFeatureById(normalizedFeatureId)

  if (feature?.href.startsWith('/monitoring')) {
    return 'Monitoring'
  }

  if (feature?.href.startsWith('/research')) {
    return 'Research'
  }

  return 'Research'
}

export function buildPlatformFeatureHref(featureId: string, subsectionId?: string) {
  const normalizedFeatureId = normalizePlatformFeatureId(featureId)
  const href = (normalizedFeatureId && FEATURE_PATHS[normalizedFeatureId]) || '/'
  return subsectionId ? `${href}?subsection=${subsectionId}` : href
}

const HOME_ITEMS: readonly PlatformNavItem[] = Object.freeze([
  {
    id: 'home',
    title: 'RBC Research',
    href: buildPlatformFeatureHref('home'),
    status: 'live',
    description: 'Mechanistic simulation, validation, and calibration for red blood cell metabolism under storage conditions, based on the Bordbar et al. (2015) reconstruction.',
    icon: 'overview',
    children: [
      {
        id: 'workspace-summary',
        title: 'About this workspace',
        description: 'Follow the blood bag from baseline chemistry into day-by-day storage drift, then into validation and calibration.',
      },
      {
        id: 'research-context',
        title: 'Researcher session',
        description: 'See the identity, workspace membership, and access state that shape the current session.',
      },
      {
        id: 'getting-started',
        title: 'Research workflow',
        description: 'Start with simulation, compare against data, then use flux, pathway, and calibration views to read the biology.',
      },
    ],
  },
  {
    id: 'home-robocop',
    title: 'RoBoCop',
    href: buildPlatformFeatureHref('home-robocop'),
    status: 'planned',
    description: 'The agent layer for guided analysis, trace review, and future human-in-the-loop support.',
    icon: 'robocop',
    children: [
      {
        id: 'agent-system',
        title: 'Agent system',
        description: 'RoBoCop coordinates product-facing agent workflows while keeping bounded scientific execution behind the FastAPI and calibration boundaries.',
      },
      {
        id: 'runtime-boundaries',
        title: 'Runtime boundaries',
        description: 'LangGraph, LangChain, and LangSmith stay internal to RoBoCop and do not replace the existing scientific backend contracts.',
      },
      {
        id: 'future-workflows',
        title: 'Future workflows',
        description: 'This page reserves a premium home for future assistant-led sessions, trace review, and human-in-the-loop research support.',
      },
    ],
  },
])

const RESEARCH_ITEMS: readonly PlatformNavItem[] = Object.freeze([
  {
    id: 'research-overview',
    title: 'Overview',
    href: buildPlatformFeatureHref('research-overview'),
    status: 'live',
    description: 'A route map of the research area, linking data upload, calibration registry, simulation, flux, and pathway tools.',
    icon: 'overview',
    children: [
      {
        id: 'research-map',
        title: 'Research map',
        description: 'Open the live analysis pages from one place before drilling into a focused task.',
      },
      {
        id: 'workflow-orientation',
        title: 'Workflow orientation',
        description: 'Move from uploads and calibration into simulation, then onward to flux and pathway work.',
      },
      {
        id: 'advanced-analysis',
        title: 'Advanced analysis',
        description: 'Keep the deeper tools aligned as the research set expands.',
      },
    ],
  },
  {
    id: 'data-upload',
    title: 'Data Upload',
    href: buildPlatformFeatureHref('data-upload'),
    status: 'live',
    description: 'Import experimental RBC storage series, map them to model metabolites, and stage them for comparison or calibration.',
    icon: 'data',
    badgeText: 'Primary',
    badgeCount: 2,
    children: [
      {
        id: 'dataset-intake',
        title: 'Upload & parse',
        description: 'Upload time-series data with automatic parsing, preview, and validation.',
      },
      {
        id: 'validation-alignment',
        title: 'Metabolite mapping',
        description: 'Match uploaded columns to model metabolites with synonym and fuzzy-name support.',
      },
      {
        id: 'data-readiness',
        title: 'Data validation',
        description: 'Check structure, time alignment, and concentration units before analysis.',
      },
    ],
  },
  {
    id: 'calibration-registry',
    title: 'Calibration Registry',
    href: buildPlatformFeatureHref('calibration-registry'),
    status: 'live',
    description: 'Inspect the historical calibration ledger, compare benchmark outcomes, and trace each record back to its evidence.',
    icon: 'calibration',
    badgeText: 'Live',
    badgeCount: 3,
    children: [
      {
        id: 'latest-record',
        title: 'Latest record',
        description: 'Inspect the newest visible calibration record, its benchmark status, and its core metrics.',
      },
      {
        id: 'benchmark-ledger',
        title: 'Benchmark ledger',
        description: 'Review grouped comparison lanes for baseline, keep, discard, and other benchmark outcomes.',
      },
      {
        id: 'artifact-trace',
        title: 'Artifact trail',
        description: 'Open the manifests, reports, and trace references that anchor each result.',
      },
    ],
  },
  {
    id: 'simulation-workspace',
    title: 'Simulation',
    href: buildPlatformFeatureHref('simulation-workspace'),
    status: 'live',
    description: 'Configure storage runs, read concentration trajectories, and explore pH-sensitive behavior across the full horizon.',
    icon: 'simulation',
    children: [
      {
        id: 'scenario-setup',
        title: 'Storage scenario',
        description: 'Shape the horizon, perturbation, fit strength, and initial conditions for each run.',
      },
      {
        id: 'solver-controls',
        title: 'Solver & tolerances',
        description: 'Pick the integrator and numerical limits that control the solve.',
      },
      {
        id: 'trajectory-review',
        title: 'Metabolite trajectories',
        description: 'Track glucose, lactate, ATP, 2,3-BPG, glutathione, and the rest of the network over time.',
      },
    ],
  },
  {
    id: 'flux-analysis',
    title: 'Flux Analysis',
    href: buildPlatformFeatureHref('flux-analysis'),
    status: 'live',
    description: 'Estimate pathway activity across glycolysis, PPP, the 2,3-BPG shunt, redox cycling, nucleotide salvage, and transport reactions.',
    icon: 'flux',
    children: [
      {
        id: 'pathway-activity',
        title: 'Pathway fluxes',
        description: 'View Michaelis-Menten flux estimates grouped by metabolic subsystem.',
      },
      {
        id: 'reaction-tracing',
        title: 'Reaction-level detail',
        description: 'Inspect key reaction rates across glycolysis, glutathione, and nucleotide reactions.',
      },
      {
        id: 'comparison-view',
        title: 'Flux comparison',
        description: 'Compare simulated fluxes against reference estimates to spot pathway gaps.',
      },
    ],
  },
  {
    id: 'pathway-visualization',
    title: 'Pathway Visualization',
    href: buildPlatformFeatureHref('pathway-visualization'),
    status: 'live',
    description: 'Explore the RBC metabolic network as a pathway map with metabolite nodes and enzyme reactions colored by subsystem.',
    icon: 'atlas',
    children: [
      {
        id: 'network-state',
        title: 'Metabolic network',
        description: 'View the complete RBC pathway map and its major reaction chains.',
      },
      {
        id: 'time-navigation',
        title: 'Concentration state',
        description: 'Overlay live metabolite concentrations to see how storage reshapes the map.',
      },
      {
        id: 'pathway-story',
        title: 'Network summary',
        description: 'Review node count, reaction count, and pathway coverage at a glance.',
      },
    ],
  },
])

export const MONITORING_ITEMS: readonly PlatformNavItem[] = Object.freeze([
  {
    id: 'monitoring-overview',
    title: 'Overview',
    href: buildPlatformFeatureHref('monitoring-overview'),
    status: 'live',
    description: 'A route-backed command center for Bag Repository, Quality Forecast, Alerts, and the future Hermes messaging gateway.',
    icon: 'overview',
    children: [
      {
        id: 'bag-repository',
        title: 'Bag Repository',
        description: 'Inspect monitored bags, metadata, and history snapshots.',
      },
      {
        id: 'quality-forecast',
        title: 'Quality Forecast',
        description: 'Read storage-quality outlooks and the drivers behind them.',
      },
      {
        id: 'alerts',
        title: 'Alerts',
        description: 'Track threshold breaches, escalations, and review state.',
      },
    ],
  },
  {
    id: 'bag-repo',
    title: 'Bag Repository',
    href: buildPlatformFeatureHref('bag-repo'),
    status: 'live',
    description: 'Browse monitored bags, donor metadata, and history snapshots in a clean route-backed inventory workspace.',
    icon: 'data',
    badgeText: 'Live',
    children: [
      {
        id: 'bag-index',
        title: 'Inventory table',
        description: 'Scan bag IDs, donor metadata, and status chips in a single structured inventory view.',
      },
      {
        id: 'bag-history',
        title: 'Bag detail',
        description: 'Open the selected bag detail rail with storage context, quality state, and alert links.',
      },
      {
        id: 'forecast-handoff',
        title: 'Forecast handoff',
        description: 'Leave room for Quality Forecast and Alerts to receive the repository record.',
      },
    ],
  },
  {
    id: 'quality-forecast',
    title: 'Quality Forecast',
    href: buildPlatformFeatureHref('quality-forecast'),
    status: 'live',
    description: 'Forecast bag quality from a limited monitoring panel, then hand projected risk into Alerts.',
    icon: 'flux',
    badgeText: 'Live',
    children: [
      {
        id: 'selected-bag',
        title: 'Selected bag',
        description: 'Keep the forecast anchored to one repository record at a time.',
      },
      {
        id: 'biomarker-panel',
        title: 'Biomarker panel',
        description: 'Use the limited extracellular monitoring panel that drives the projection.',
      },
      {
        id: 'trajectory',
        title: 'Trajectory & handoff',
        description: 'Read the projected curve and move into Alerts when the watch band tightens.',
      },
    ],
  },
  {
    id: 'alerts',
    title: 'Alerts',
    href: buildPlatformFeatureHref('alerts'),
    status: 'live',
    description: 'Turn forecast risk into prioritized review items, operator actions, and escalation state.',
    icon: 'prompts',
    badgeText: 'Live',
    children: [
      {
        id: 'alert-queue',
        title: 'Alert queue',
        description: 'Forecast-derived risk items, severity, and workflow state stay visible in one queue.',
      },
      {
        id: 'alert-policy',
        title: 'Alert policy',
        description: 'Explain why an alert fired, what to do next, and how the review state evolves.',
      },
      {
        id: 'operator-actions',
        title: 'Operator actions',
        description: 'Acknowledge, escalate, or resolve alerts while keeping Bag Repository and Forecast one click away.',
      },
    ],
  },
])

const HIDDEN_FEATURE_ITEMS: readonly PlatformNavItem[] = Object.freeze([
  {
    id: 'parameter-calibration',
    title: 'Parameter Calibration',
    href: buildPlatformFeatureHref('parameter-calibration'),
    status: 'live',
    description: 'Optimize kinetic parameters against experimental storage data to improve agreement with observed trajectories.',
    icon: 'calibration',
    children: [
      {
        id: 'target-scope',
        title: 'Parameter selection',
        description: 'Choose the Vmax and Km parameters to fit across glycolysis, transport, and salvage reactions.',
      },
      {
        id: 'parameter-scope',
        title: 'Optimization method',
        description: 'Select the optimization strategy and iteration budget for the search.',
      },
      {
        id: 'benchmark-review',
        title: 'Calibration results',
        description: 'Review optimized values, fit quality, and relative parameter shifts.',
      },
    ],
  },
  {
    id: 'monitoring-robocop',
    title: 'Hermes',
    href: buildPlatformFeatureHref('monitoring-robocop'),
    status: 'planned',
    description: 'Future messaging gateway for Monitoring, starting with Telegram routing and operator-facing alerts.',
    icon: 'prompts',
    badgeText: 'Future',
    children: [
      {
        id: 'gateway-setup',
        title: 'Gateway setup',
        description: 'Hermes will broker operational messages into Monitoring once the routing layer is ready.',
      },
      {
        id: 'telegram-first',
        title: 'Telegram first',
        description: 'Telegram is the first planned outbound surface for operator notifications.',
      },
    ],
  },
])

export const PLATFORM_NAV_SECTIONS: readonly PlatformNavSection[] = Object.freeze([
  {
    id: 'home',
    label: 'HOME',
    collapsible: false,
    items: [...HOME_ITEMS],
  },
  {
    id: 'research',
    label: 'RESEARCH',
    collapsible: false,
    items: [...RESEARCH_ITEMS],
  },
  {
    id: 'monitoring',
    label: 'MONITORING',
    collapsible: false,
    items: [...MONITORING_ITEMS],
  },
])

const PLATFORM_NAV_ITEMS = [...PLATFORM_NAV_SECTIONS.flatMap(section => section.items), ...HIDDEN_FEATURE_ITEMS]

export function getPlatformFeatureById(featureId?: string | null) {
  const normalizedFeatureId = normalizePlatformFeatureId(featureId)
  if (!normalizedFeatureId) {
    return null
  }

  return PLATFORM_NAV_ITEMS.find(item => item.id === normalizedFeatureId) ?? null
}

export function getActivePlatformFeatureId(pathname?: string | null, legacyFeatureId?: string | null) {
  const normalizedPathname = pathname || '/'
  const normalizedLegacyFeatureId = normalizePlatformFeatureId(legacyFeatureId)

  if (normalizedPathname === '/' && normalizedLegacyFeatureId && normalizedLegacyFeatureId !== 'home') {
    return normalizedLegacyFeatureId
  }

  const exactMatch = PLATFORM_NAV_ITEMS.find(item => item.href === normalizedPathname)

  if (exactMatch) {
    return exactMatch.id
  }

  const matchedFeature = PLATFORM_NAV_ITEMS
    .filter(item => item.href !== '/' && normalizedPathname.startsWith(`${item.href}/`))
    .sort((left, right) => right.href.length - left.href.length)[0]

  return matchedFeature?.id ?? (normalizedPathname === '/' ? 'home' : null)
}

export function getPlatformFeatureSelection(featureId?: string | null, subsectionId?: string | null) {
  const feature = getPlatformFeatureById(featureId)
  const subsection = feature?.children?.find(item => item.id === subsectionId) ?? feature?.children?.[0] ?? null

  return {
    feature,
    subsection,
  }
}

export const PLATFORM_MODULE_CARDS: readonly PlatformModuleCard[] = Object.freeze([
  {
    title: 'Simulation',
    status: 'live',
    description: 'Tune storage horizons and solver settings, then follow how the metabolome changes.',
    eyebrow: 'Scenario lab',
    icon: 'simulation',
    href: buildPlatformFeatureHref('simulation-workspace'),
  },
  {
    title: 'Data Upload',
    status: 'live',
    description: 'Import experimental series, verify their structure, and stage them for comparison or calibration.',
    eyebrow: 'Evidence intake',
    icon: 'data',
    href: buildPlatformFeatureHref('data-upload'),
  },
  {
    title: 'Calibration Registry',
    status: 'live',
    description: 'Inspect the calibration ledger and the evidence trail behind each benchmarked run.',
    eyebrow: 'Run ledger',
    icon: 'calibration',
    href: buildPlatformFeatureHref('calibration-registry'),
  },
  {
    title: 'Parameter Calibration',
    status: 'live',
    description: 'Search for kinetic settings that narrow model error.',
    eyebrow: 'Tuning bench',
    icon: 'calibration',
    href: buildPlatformFeatureHref('parameter-calibration'),
  },
  {
    title: 'Flux Analysis',
    status: 'live',
    description: 'Read pathway activity and reaction shifts across the RBC metabolic network.',
    eyebrow: 'Pathway audit',
    icon: 'flux',
    href: buildPlatformFeatureHref('flux-analysis'),
  },
  {
    title: 'Pathway Visualization',
    status: 'live',
    description: 'Trace the network map as storage reshapes metabolite flow.',
    eyebrow: 'Network atlas',
    icon: 'atlas',
    href: buildPlatformFeatureHref('pathway-visualization'),
  },
  {
    title: 'RoBoCop',
    status: 'planned',
    description: 'Reserve the assistant layer for guided research and monitoring work.',
    eyebrow: 'Agent layer',
    icon: 'robocop',
    href: buildPlatformFeatureHref('home-robocop'),
  },
])

export const SIDEBAR_SUPPORT_SECTIONS: readonly SidebarSupportSection[] = Object.freeze([
  {
    id: 'about',
    eyebrow: 'About',
    title: 'RBC Metabolic Model v2.0',
    description:
      'Mechanistic red blood cell metabolism workspace based on the Bordbar et al. (2015) reconstruction, with support for simulation, validation, pathway interpretation, and exploratory calibration.',
    bullets: [
      'Storage-condition simulation',
      'Experimental dataset comparison',
      'Pathway and flux exploration',
      'Calibration-oriented analysis',
    ],
  },
  {
    id: 'resources',
    eyebrow: 'Resources',
    title: 'Research references',
    links: [
      {
        label: 'Original Article',
        href: 'https://www.cell.com/action/showPdf?pii=S2405-4712%2815%2900149-0',
        external: true,
      },
      {
        label: 'Project documentation is available in the repository workspace.',
      },
      {
        label: 'Use Data Upload to validate against your own experimental series.',
      },
    ],
  },
  {
    id: 'tips',
    eyebrow: 'Tips',
    title: 'New to the workspace?',
    description:
      'Start with the default simulation settings, then move into flux analysis or pathway visualization to interpret the resulting RBC storage trajectory.',
    tone: 'success',
  },
])

export const SIDEBAR_ACCOUNT_ACTIONS: readonly SidebarAccountAction[] = Object.freeze([
  {
    title: 'View Profile',
    href: '/account',
    icon: 'account',
  },
  {
    title: 'Upgrade Plan',
    href: '/billing/upgrade',
    icon: 'billing',
    badgeText: 'Pro',
  },
  {
    title: 'Account Settings',
    href: '/account/settings',
    icon: 'settings',
  },
  {
    title: 'Billing',
    href: '/billing',
    icon: 'billing',
  },
  {
    title: 'Sign out',
    href: '/auth/signout',
    icon: 'account',
    tone: 'danger',
  },
])
