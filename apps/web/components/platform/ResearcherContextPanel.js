import { createElement as h } from 'react'
import { FieldGrid } from '../ui/FieldGrid.js'
import { MetricGrid } from '../ui/MetricGrid.js'

export function ResearcherContextPanel({ productContext, access, visibleRunCount = null }) {
  const metrics = [
    ['Access mode', access?.mode || 'unknown'],
    ['Workspace memberships', productContext?.workspaceMemberships?.length || 0],
    ['Stored preference', productContext?.storedWorkspacePreferenceState || 'unknown'],
    ['Visible runs', visibleRunCount],
  ]

  const fields = [
    ['Researcher', productContext?.researcherIdentity?.displayName],
    ['Email', productContext?.researcherIdentity?.email],
    ['Organization', productContext?.researcherIdentity?.organizationName],
    ['Active workspace', productContext?.activeWorkspace?.name || productContext?.activeWorkspace?.slug],
    ['Membership role', productContext?.workspaceMembership?.membershipRole],
    ['Context state', productContext?.contextState],
  ]

  return h('section', { className: 'panel' }, [
    h('div', { className: 'panel-heading', key: 'heading' }, [
      h('h2', { key: 'title' }, 'Researcher context'),
      h('p', { key: 'copy' }, 'Authenticated user identity, workspace linkage, and request-level access posture resolved on the server.'),
    ]),
    h(MetricGrid, { metrics, key: 'metrics' }),
    h(FieldGrid, { fields, key: 'fields' }),
  ])
}
