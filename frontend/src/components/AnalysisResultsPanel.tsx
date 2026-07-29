import type { LinkedAnalysisResult } from '../utils/analysisResult'

const LABEL_CLASSES = {
  안전: 'text-bg-success',
  주의: 'text-bg-warning',
  위험: 'text-bg-danger',
  '추가 확인': 'text-bg-secondary',
} as const

type AnalysisResultsPanelProps = Readonly<{
  isLoading: boolean
  results: LinkedAnalysisResult[] | null
  error: string | null
}>

export function AnalysisResultsPanel({
  isLoading,
  results,
  error,
}: AnalysisResultsPanelProps) {
  if (!isLoading && results === null && error === null) return null

  return (
    <section aria-labelledby="analysis-results-title" aria-busy={isLoading}>
      <h2 id="analysis-results-title" className="h4 mb-3">
        분석 결과
      </h2>
      <p className="alert alert-secondary">
        표시된 결과는 합성 Provider를 사용한 화면·API 흐름 검증용 결과입니다.
        법률 자문이나 최종 판단을 제공하지 않습니다.
      </p>
      <div aria-live="polite">
        {isLoading && <p className="alert alert-info">분석 결과를 불러오고 있습니다.</p>}
      </div>
      {error && <p className="alert alert-danger" role="alert">{error}</p>}
      {!isLoading && results && results.length === 0 && (
        <p className="alert alert-secondary">표시할 분석 결과가 없습니다.</p>
      )}
      {!isLoading && results && results.length > 0 && (
        <div className="d-grid gap-3">
          {results.map(({ clause, result }) => (
            <article className="card border-0 shadow-sm" key={result.reference_id}>
              <div className="card-body p-4">
                <div className="item-metadata d-flex flex-wrap align-items-center gap-2 mb-2">
                  <span className="badge text-bg-secondary">{clause.ordinal}번째 조항</span>
                  {clause.marker && <span className="item-text fw-semibold">{clause.marker}</span>}
                  {clause.clause_type && <span className="item-text text-secondary small">{clause.clause_type}</span>}
                  <span className={`result-label badge ${LABEL_CLASSES[result.display_label]}`}>
                    {result.display_label}
                  </span>
                </div>
                {clause.title && <h3 className="item-title h5">{clause.title}</h3>}
                <p className="analysis-summary mb-3">{result.summary}</p>
                <p className="mb-0 fw-semibold">
                  {result.expert_review_recommended
                    ? '전문가 검토를 권고합니다.'
                    : '별도 권고가 표시되지 않았습니다.'}
                </p>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
