export type StatusTone = 'ok' | 'warn' | 'blocked' | 'unknown'

/** A fact, not a control: dot + label + value (+ optional detail). Never clickable. */
export function StatusLine({ tone = 'unknown', label, value, detail }: {
  tone?: StatusTone
  label: string
  value: string
  detail?: string | null
}) {
  return (
    <div className="r-status" data-tone={tone} data-status={label}>
      <span className="r-status-label">{label}</span>
      <span className="r-status-value">{value}</span>
      {detail ? <span className="r-status-detail">{detail}</span> : null}
    </div>
  )
}

/** Tone of a yes/no/unchecked answer such as data_valid or launch_allowed. */
export function answerTone(value: boolean | null | undefined): StatusTone {
  return value === true ? 'ok' : value === false ? 'blocked' : 'unknown'
}
