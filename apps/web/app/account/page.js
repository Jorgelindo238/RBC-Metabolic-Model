import { createElement as h } from 'react'
import { getServerProductContext } from '../../lib/server-product-context.mjs'
import { FieldGrid } from '../../components/ui/FieldGrid.js'

export default async function Page() {
  const productContext = await getServerProductContext()
  const identity = productContext?.researcherIdentity

  return h('main', { className: 'page-shell' }, [
    h('section', { className: 'panel', key: 'account' }, [
      h('p', { className: 'eyebrow', key: 'eyebrow' }, 'My account'),
      h('h1', { className: 'page-title', key: 'title' }, 'Researcher account'),
      h('p', { className: 'page-copy', key: 'copy' }, 'This product-layer surface anchors account identity and gives the premium shell a real account destination without broadening into a larger settings system.'),
      h(FieldGrid, {
        fields: [
          ['Display name', identity?.displayName],
          ['Email', identity?.email],
          ['Organization', identity?.organizationName],
          ['Context state', productContext?.contextState],
        ],
        key: 'fields',
      }),
    ]),
  ])
}
