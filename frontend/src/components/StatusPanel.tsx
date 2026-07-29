type StatusPanelProps = Readonly<{
  title: string
  description: string
}>

export function StatusPanel({
  title,
  description,
}: StatusPanelProps) {
  return (
    <section className="card border-0 shadow-sm" aria-labelledby="status-title">
      <div className="card-body p-4 p-md-5">
        <span className="badge text-bg-primary mb-3">로컬 통합 준비</span>
        <h2 id="status-title" className="h4">
          {title}
        </h2>
        <p className="text-secondary mb-0">{description}</p>
      </div>
    </section>
  )
}
