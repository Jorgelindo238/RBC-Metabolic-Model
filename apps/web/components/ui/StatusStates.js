import { createElement as h } from 'react'
import Link from 'next/link'

export function DatabaseUnreachableState({ showBackLink = false }) {
  return h('main', { className: 'page-shell' }, [
    h('section', { className: 'panel' }, [
      showBackLink ? h(Link, { href: '/', className: 'back-link', key: 'back' }, '← Back to run list') : null,
      h('h1', { className: 'page-title', key: 'title' }, 'Database Unreachable'),
      h('p', { className: 'page-copy', key: 'copy' }, 'Supabase credentials are not configured in this environment.')
    ].filter(Boolean))
  ])
}

export function ErrorState({ error, showBackLink = false }) {
  return h('main', { className: 'page-shell' }, [
    h('section', { className: 'panel' }, [
      showBackLink ? h(Link, { href: '/', className: 'back-link', key: 'back' }, '← Back to run list') : null,
      h('h1', { className: 'page-title', key: 'title' }, 'Error Loading Data'),
      h('p', { className: 'page-copy', key: 'copy' }, String(error))
    ].filter(Boolean))
  ])
}

export function EmptyState({ message = 'No runs available.' }) {
  return h('main', { className: 'page-shell' }, [
    h('section', { className: 'panel' }, [
      h('h1', { className: 'page-title', key: 'title' }, message)
    ])
  ])
}
