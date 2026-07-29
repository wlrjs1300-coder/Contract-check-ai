import type { AnalysisJob } from '../types/analysisJobs'
import type { UploadedDocument } from '../types/documents'
import { AnalysisJobPanel } from '../components/AnalysisJobPanel'
import { AnalysisStepper } from '../components/AnalysisStepper'
import { ClauseList } from '../components/ClauseList'
import { DocumentSummary } from '../components/DocumentSummary'
import { DocumentUploadForm } from '../components/DocumentUploadForm'
import { UnclassifiedSections } from '../components/UnclassifiedSections'

type AnalyzePageProps = Readonly<{
  selectedFile: File | null
  uploadStatus: 'idle' | 'selected' | 'uploading' | 'success' | 'error'
  uploadError: string | null
  document: UploadedDocument | null
  job: AnalysisJob | null
  isCreating: boolean
  isRefreshing: boolean
  isLoadingResults: boolean
  requestError: string | null
  refreshError: string | null
  resultsError: string | null
  hasResults: boolean
  onFileChange: (file: File | null) => void
  onUpload: () => void
  onStart: () => void
  onRefresh: () => void
  onViewResults: () => void
}>

export function AnalyzePage(props: AnalyzePageProps) {
  const busy = props.isCreating || props.isRefreshing || props.isLoadingResults
  const currentStep = props.document === null ? 1 : props.job === null ? 2 : props.job.status === 'completed' ? 4 : 3
  const completedThrough = props.hasResults ? 4 : props.document === null ? 0 : props.job === null ? 1 : props.job.status === 'completed' ? 3 : 2
  const previewClauses = props.document?.clauses.slice(0, 3) ?? []

  return (
    <div className="page analyze-page">
      <header className="page-heading">
        <div>
          <p className="section-label">Document analysis</p>
          <h1>계약서 분석</h1>
          <p>파일 등록, 조항 확인, 분석 요청을 순서대로 진행합니다.</p>
        </div>
        <span className="scope-chip">TXT · 최대 1MB</span>
      </header>
      <AnalysisStepper currentStep={currentStep} completedThrough={completedThrough} />
      <div className="analyze-layout">
        <DocumentUploadForm
          selectedFile={props.selectedFile}
          isUploading={props.uploadStatus === 'uploading'}
          isDisabled={busy}
          onFileChange={props.onFileChange}
          onSubmit={props.onUpload}
        />
        <div className="page-message">
          {props.uploadStatus === 'uploading' && <p className="alert alert-info" role="status">문서를 업로드하고 있습니다.</p>}
          {props.uploadError && <p className="alert alert-danger" role="alert">{props.uploadError}</p>}
          {props.resultsError && <p className="alert alert-danger" role="alert">{props.resultsError}</p>}
        </div>
        {props.document && (
          <div className="document-workspace">
            <DocumentSummary document={props.document} />
            <AnalysisJobPanel
              canStart={props.document.document_id.trim().length > 0 && props.document.clauses.length > 0}
              isCreating={props.isCreating}
              isRefreshing={props.isRefreshing}
              isLoadingResults={props.isLoadingResults}
              job={props.job}
              requestError={props.requestError}
              refreshError={props.refreshError}
              onStart={props.onStart}
              onRefresh={props.onRefresh}
              onViewResults={props.onViewResults}
            />
            <UnclassifiedSections sections={props.document.unclassified_sections} />
            <ClauseList clauses={previewClauses} />
            {props.document.clauses.length > previewClauses.length && (
              <p className="preview-note">처음 3개 조항만 미리 표시합니다. 전체 조항은 분석 결과 화면에서 탐색할 수 있습니다.</p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
