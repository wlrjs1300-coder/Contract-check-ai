import type { DocumentClause } from '../types/documents'
import { WarningList } from './WarningList'

type ClauseListProps = Readonly<{
  clauses: DocumentClause[]
}>

export function ClauseList({ clauses }: ClauseListProps) {
  const orderedClauses = [...clauses].sort(
    (left, right) => left.ordinal - right.ordinal,
  )

  return (
    <section aria-labelledby="clauses-title">
      <h2 id="clauses-title" className="h4 mb-3">
        분리된 조항
      </h2>

      {orderedClauses.length === 0 ? (
        <p className="alert alert-secondary mb-0">
          분리된 조항이 없습니다. 문서 형식과 조항 표기를 확인해 주세요.
        </p>
      ) : (
        <div className="d-grid gap-3">
          {orderedClauses.map((clause) => (
            <article className="card border-0 shadow-sm" key={clause.reference_id}>
              <div className="card-body p-4">
                <div className="item-metadata d-flex flex-wrap align-items-center gap-2 mb-2">
                  <span className="badge text-bg-secondary">
                    {clause.ordinal}번째 조항
                  </span>
                  {clause.marker && <span className="item-text fw-semibold">{clause.marker}</span>}
                  {clause.clause_type && (
                    <span className="item-text text-secondary small">{clause.clause_type}</span>
                  )}
                </div>
                {clause.title && <h3 className="item-title h5">{clause.title}</h3>}
                <p className="clause-body mb-3">{clause.body || '본문이 없습니다.'}</p>
                <WarningList warnings={clause.warnings} title="조항 처리 확인 정보" />
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
