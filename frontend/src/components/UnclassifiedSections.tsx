type UnclassifiedSectionsProps = Readonly<{
  sections: string[]
}>

export function UnclassifiedSections({ sections }: UnclassifiedSectionsProps) {
  if (sections.length === 0) {
    return null
  }

  return (
    <section className="card" aria-labelledby="unclassified-title">
      <div className="card-body">
        <h2 id="unclassified-title" className="h4">
          미분류 영역
        </h2>
        <p className="text-secondary">
          조항 표기 패턴으로 분류되지 않은 원문 영역입니다.
        </p>
        <ol className="list-group list-group-numbered">
          {sections.map((section, index) => (
            <li
              className="list-group-item unclassified-text"
              key={`${index}-${section}`}
            >
              {section}
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}
