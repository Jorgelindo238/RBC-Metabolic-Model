import { createElement as h } from 'react'

export default function Page() {
  return h('main', { className: 'page-shell' }, [
    h('section', { className: 'panel', key: 'settings' }, [
      h('p', { className: 'eyebrow', key: 'eyebrow' }, 'Account settings'),
      h('h1', { className: 'page-title', key: 'title' }, 'Account settings'),
      h('p', { className: 'page-copy', key: 'copy' }, 'This reserved settings surface prepares the shell for future researcher preferences, notification controls, workspace settings, and linked-channel settings without implementing that larger system in this phase.'),
    ]),
  ])
}
