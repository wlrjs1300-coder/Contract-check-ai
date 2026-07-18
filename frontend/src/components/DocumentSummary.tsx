import type { UploadedDocument } from '../types/documents'
import { formatFileSize } from '../utils/documentUpload'
import { WarningList } from './WarningList'

type DocumentSummaryProps = Readonly<{
  document: UploadedDocument
}>

export function DocumentSummary({ document }: DocumentSummaryProps) {
  return (
    <section className="card" aria-labelledby="summary-title">
      <div className="card-body">
        <h2 id="summary-title" className="h4">
          업로드 결과
        </h2>
        <dl className="document-summary mb-4">
          <div>
            <dt>파일명</dt>
            <dd>{document.filename}</dd>
          </div>
          <div>
            <dt>파일 크기</dt>
            <dd>{formatFileSize(document.size_bytes)}</dd>
          </div>
          <div>
            <dt>문자 수</dt>
            <dd>{document.character_count.toLocaleString('ko-KR')}</dd>
          </div>
          <div>
            <dt>문서 처리 상태</dt>
            <dd>{document.status}</dd>
          </div>
          <div>
            <dt>분리된 조항 수</dt>
            <dd>{document.clause_count.toLocaleString('ko-KR')}</dd>
          </div>
        </dl>

        <WarningList
          warnings={document.document_warnings}
          title="문서 처리 확인 정보"
        />
      </div>
    </section>
  )
}
