const WARNING_MESSAGES: Readonly<Record<string, string>> = {
  no_clause_marker_detected: '인식할 수 있는 조항 표기를 찾지 못했습니다.',
  empty_body: '조항 본문이 비어 있습니다.',
}

type WarningListProps = Readonly<{
  warnings: string[]
  title: string
}>

export function WarningList({ warnings, title }: WarningListProps) {
  if (warnings.length === 0) {
    return null
  }

  return (
    <div className="alert alert-warning mb-0">
      <p className="fw-semibold mb-2">{title}</p>
      <ul className="mb-0">
        {warnings.map((warning, index) => (
          <li key={`${warning}-${index}`}>
            {WARNING_MESSAGES[warning] ?? warning}
          </li>
        ))}
      </ul>
    </div>
  )
}
