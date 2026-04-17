import { Suspense, createElement as h } from 'react'
import { PlatformSidebar } from './PlatformSidebar.js'
import { PlatformHeader } from './PlatformHeader.js'

export function PlatformShell({ productContext, children }) {
  return h('div', { className: 'platform-shell' }, [
    h(Suspense, { fallback: null, key: 'sidebar-boundary' }, h(PlatformSidebar, { productContext })),
    h('div', { className: 'platform-content', key: 'content' }, [
      h(PlatformHeader, { productContext, key: 'header' }),
      children,
    ]),
  ])
}
