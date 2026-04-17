import { SIDEBAR_SUPPORT_SECTIONS } from '../../lib/platform-navigation.ts'

export function SidebarSupportPanels({ compact }: { compact: boolean }) {
  if (compact) {
    return null
  }

  return (
    <div className="sidebar-support-stack">
      {SIDEBAR_SUPPORT_SECTIONS.map(section => (
        <details
          className={`sidebar-support-panel${section.tone === 'success' ? ' sidebar-support-panel-success' : ''}`}
          key={section.id}
        >
          <summary className="sidebar-support-summary">
            <div className="sidebar-support-summary-copy">
              <p className="sidebar-support-eyebrow">{section.eyebrow}</p>
              <h3 className="sidebar-support-title">{section.title}</h3>
            </div>
            <span className="sidebar-support-chevron" aria-hidden="true">
              ⌄
            </span>
          </summary>
          <div className="sidebar-support-body">
            {section.description ? <p className="sidebar-support-copy">{section.description}</p> : null}
            {section.bullets?.length ? (
              <ul className="sidebar-support-list">
                {section.bullets.map(item => (
                  <li className="sidebar-support-list-item" key={item}>
                    {item}
                  </li>
                ))}
              </ul>
            ) : null}
            {section.links?.length ? (
              <div className="sidebar-support-links">
                {section.links.map(link =>
                  link.href ? (
                    <a
                      className="sidebar-support-link"
                      href={link.href}
                      key={link.label}
                      rel={link.external ? 'noreferrer' : undefined}
                      target={link.external ? '_blank' : undefined}
                    >
                      {link.label}
                    </a>
                  ) : (
                    <p className="sidebar-support-copy sidebar-support-copy-muted" key={link.label}>
                      {link.label}
                    </p>
                  )
                )}
              </div>
            ) : null}
          </div>
        </details>
      ))}
    </div>
  )
}
