export const PLATFORM_NAV_SECTIONS = Object.freeze([
  {
    label: 'Platform',
    items: [
      {
        title: 'Overview',
        href: '/',
        status: 'live',
        description: 'Research platform home and current access context.',
      },
      {
        title: 'Calibration Registry',
        href: '/',
        status: 'live',
        description: 'Authenticated browse surface for persisted calibration runs.',
      },
    ],
  },
  {
    label: 'Research Workspaces',
    items: [
      {
        title: 'Simulation Workspace',
        href: null,
        status: 'planned',
        description: 'Launch and inspect bounded simulation workflows downstream of Python.',
      },
      {
        title: 'Data Hub',
        href: null,
        status: 'planned',
        description: 'Bring experimental datasets into comparison and validation flows.',
      },
      {
        title: 'Flux Analysis',
        href: null,
        status: 'planned',
        description: 'Inspect pathway activity and reaction-level behavior.',
      },
      {
        title: 'RBC Metabolic Atlas',
        href: null,
        status: 'planned',
        description: 'Explore pathway structure and time-dependent network state.',
      },
    ],
  },
  {
    label: 'RoBoCop Layer',
    items: [
      {
        title: 'RoBoCop Sessions',
        href: null,
        status: 'planned',
        description: 'Future agent sessions, triage notes, and guided scientific actions.',
      },
    ],
  },
])

export const PLATFORM_MODULE_CARDS = Object.freeze([
  {
    title: 'Calibration Intelligence',
    status: 'live',
    description: 'Browse registry-backed calibration evidence, run summaries, and artifact references with authenticated server-side reads.',
    eyebrow: 'Live now',
  },
  {
    title: 'Simulation Workspace',
    status: 'planned',
    description: 'Future researcher surface for bounded simulation launches and comparison workflows inspired by the Streamlit simulation workspace.',
    eyebrow: 'Planned next',
  },
  {
    title: 'Data Hub',
    status: 'planned',
    description: 'Future ingestion and validation surface for uploaded experimental datasets and mapping workflows.',
    eyebrow: 'Platform direction',
  },
  {
    title: 'RBC Metabolic Atlas',
    status: 'planned',
    description: 'Future pathway and network interpretation module informed by the Streamlit pathway visualization and flux pages.',
    eyebrow: 'Research navigation',
  },
  {
    title: 'Flux Analysis',
    status: 'planned',
    description: 'Future inspection area for pathway activity, case-level context, and metabolite-to-flux interpretation.',
    eyebrow: 'Reserved module',
  },
  {
    title: 'RoBoCop Sessions',
    status: 'planned',
    description: 'Future assistant-led research workflows backed by Supabase product context and bounded scientific execution.',
    eyebrow: 'Future agent layer',
  },
])
