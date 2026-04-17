import { createElement as h } from 'react'
import { PLATFORM_MODULE_CARDS } from '../../lib/platform-navigation.mjs'

function ModuleCard({ card }) {
  return h('article', { className: 'module-card' }, [
    h('p', { className: 'module-card-eyebrow', key: 'eyebrow' }, card.eyebrow),
    h('div', { className: 'module-card-header', key: 'header' }, [
      h('h3', { className: 'module-card-title', key: 'title' }, card.title),
      h('span', { className: `platform-status-chip status-${card.status}`, key: 'status' }, card.status),
    ]),
    h('p', { className: 'module-card-copy', key: 'copy' }, card.description),
  ])
}

export function ModuleCards() {
  return h('div', { className: 'module-card-grid' }, PLATFORM_MODULE_CARDS.map(card => h(ModuleCard, { card, key: card.title })))
}
