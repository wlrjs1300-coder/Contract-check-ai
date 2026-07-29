import { useState } from 'react'
import type { UploadedDocument } from '../types/documents'
import type { LinkedAnalysisResult } from '../utils/analysisResult'
import type { AppPage } from '../components/TopNavigation'
import { formatFileSize } from '../utils/documentUpload'

const LABEL_CLASSES = {
  안전: 'text-bg-success',
  주의: 'text-bg-warning',
  위험: 'text-bg-danger',
  '추가 확인': 'text-bg-secondary',
} as const

type ResultsPageProps = Readonly<{
  document: UploadedDocument | null
  results: LinkedAnalysisResult[] | null
  error: string | null
  onNavigate: (page: AppPage) => void
}>

export function ResultsPage({ document, results, error, onNavigate }: ResultsPageProps) {
  const [selectedIndex, setSelectedIndex] = useState(0)

  if (document === null || results === null || results.length === 0) {
    return (
      <div className="page empty-results-page">
        <p className="section-label">Analysis results</p>
        <h1>검토 결과</h1>
        {error ? <p className="alert alert-danger" role="alert">{error}</p> : (
          <p>표시할 분석 결과가 없습니다. 문서를 업로드하고 분석을 완료해 주세요.</p>
        )}
        <button type="button" className="btn btn-primary" onClick={() => onNavigate('analyze')}>
          계약서 분석으로 이동
        </button>
      </div>
    )
  }

  const safeIndex = Math.min(selectedIndex, results.length - 1)
  const selected = results[safeIndex]
  const { clause, result } = selected

  return (
    <div className="page results-page">
      <header className="results-header">
        <div>
          <p className="section-label">Analysis results</p>
          <h1>검토 결과</h1>
        </div>
        <dl>
          <div><dt>문서명</dt><dd>{document.filename}</dd></div>
          <div><dt>크기</dt><dd>{formatFileSize(document.size_bytes)}</dd></div>
          <div><dt>조항</dt><dd>{document.clause_count.toLocaleString('ko-KR')}개</dd></div>
        </dl>
        <button type="button" className="btn btn-outline-primary" onClick={() => onNavigate('analyze')}>
          새 문서 분석
        </button>
      </header>

      <p className="result-boundary">
        합성 Provider 기반 화면·API 흐름 검증 결과이며 법률 자문이나 최종 판단이 아닙니다.
      </p>

      <section className="result-browser" aria-labelledby="result-detail-title">
        <nav className="clause-navigation" aria-label="검토 결과 조항 목록">
          <p>조항 목록</p>
          <ol>
            {results.map((item, index) => (
              <li key={item.result.reference_id}>
                <button
                  type="button"
                  aria-current={index === safeIndex ? 'true' : undefined}
                  aria-label={`${item.clause.ordinal}번째 조항 선택${item.clause.title ? `: ${item.clause.title}` : ''}`}
                  onClick={() => setSelectedIndex(index)}
                >
                  <span>{String(item.clause.ordinal).padStart(2, '0')}</span>
                  <strong>{item.clause.marker || `${item.clause.ordinal}번째 조항`}</strong>
                  <small>{item.clause.title || '제목 없음'}</small>
                </button>
              </li>
            ))}
          </ol>
        </nav>

        <article className="result-detail">
          <div className="result-detail-meta">
            <span>{clause.ordinal}번째 조항</span>
            {clause.clause_type && <span>{clause.clause_type}</span>}
            <span className={`result-label badge ${LABEL_CLASSES[result.display_label]}`}>
              {result.display_label}
            </span>
          </div>
          <h2 id="result-detail-title">{clause.title || clause.marker || '제목 없는 조항'}</h2>
          <section aria-labelledby="clause-source-title">
            <h3 id="clause-source-title">조항 원문</h3>
            <p className="clause-body">{clause.body || '본문이 없습니다.'}</p>
          </section>
          <section aria-labelledby="result-summary-title">
            <h3 id="result-summary-title">분석 요약</h3>
            <p className="analysis-summary">{result.summary}</p>
          </section>
          <p className="expert-review">
            {result.expert_review_recommended
              ? '전문가 검토를 권고합니다.'
              : '별도 권고가 표시되지 않았습니다.'}
          </p>
        </article>
      </section>

      <nav className="result-pagination" aria-label="조항 페이지 이동">
        <button type="button" disabled={safeIndex === 0} onClick={() => setSelectedIndex(safeIndex - 1)}>
          이전 조항
        </button>
        <span><strong>{safeIndex + 1}</strong> / {results.length}</span>
        <button type="button" disabled={safeIndex === results.length - 1} onClick={() => setSelectedIndex(safeIndex + 1)}>
          다음 조항
        </button>
      </nav>
    </div>
  )
}
