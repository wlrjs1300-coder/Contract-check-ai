import { useState } from 'react'
import { createAnalysisJob, getAnalysisJob } from '../api/analysisJobs'
import { getAnalysisResults } from '../api/analysisResults'
import { uploadDocument } from '../api/documents'
import { AnalysisJobPanel } from '../components/AnalysisJobPanel'
import { AnalysisResultsPanel } from '../components/AnalysisResultsPanel'
import { ClauseList } from '../components/ClauseList'
import { DocumentSummary } from '../components/DocumentSummary'
import { DocumentUploadForm } from '../components/DocumentUploadForm'
import { UnclassifiedSections } from '../components/UnclassifiedSections'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import brandMark from '../assets/brand-mark.svg'
import type { UploadedDocument } from '../types/documents'
import type { AnalysisJob } from '../types/analysisJobs'
import type { LinkedAnalysisResult } from '../utils/analysisResult'
import {
  ANALYSIS_LINK_ERROR_MESSAGE,
  getAnalysisResultsErrorMessage,
  linkAnalysisResults,
} from '../utils/analysisResult'
import {
  getAnalysisRefreshErrorMessage,
  getAnalysisRequestErrorMessage,
} from '../utils/analysisJob'
import {
  getUploadErrorMessage,
  validateUploadFile,
} from '../utils/documentUpload'

type UploadStatus = 'idle' | 'selected' | 'uploading' | 'success' | 'error'

export function ScaffoldPage() {
  useDocumentTitle('ContractCheck AI')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [status, setStatus] = useState<UploadStatus>('idle')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [document, setDocument] = useState<UploadedDocument | null>(null)
  const [analysisJob, setAnalysisJob] = useState<AnalysisJob | null>(null)
  const [isCreatingAnalysis, setIsCreatingAnalysis] = useState(false)
  const [isRefreshingAnalysis, setIsRefreshingAnalysis] = useState(false)
  const [analysisRequestError, setAnalysisRequestError] = useState<string | null>(null)
  const [analysisRefreshError, setAnalysisRefreshError] = useState<string | null>(null)
  const [isLoadingResults, setIsLoadingResults] = useState(false)
  const [analysisResults, setAnalysisResults] = useState<LinkedAnalysisResult[] | null>(null)
  const [analysisResultsError, setAnalysisResultsError] = useState<string | null>(null)
  const isAnalysisBusy = isCreatingAnalysis || isRefreshingAnalysis || isLoadingResults

  function resetResultsState() {
    setIsLoadingResults(false)
    setAnalysisResults(null)
    setAnalysisResultsError(null)
  }

  function resetAnalysisState() {
    setAnalysisJob(null)
    setIsCreatingAnalysis(false)
    setIsRefreshingAnalysis(false)
    setAnalysisRequestError(null)
    setAnalysisRefreshError(null)
    resetResultsState()
  }

  function handleFileChange(file: File | null) {
    setSelectedFile(file)
    setStatus(file ? 'selected' : 'idle')
    setErrorMessage(null)
    setDocument(null)
    resetAnalysisState()
  }

  async function handleUpload() {
    if (status === 'uploading' || isAnalysisBusy) {
      return
    }

    const file = selectedFile
    const validationMessage = validateUploadFile(file)

    if (validationMessage) {
      setStatus('error')
      setErrorMessage(validationMessage)
      return
    }

    if (file === null) {
      return
    }

    setStatus('uploading')
    setErrorMessage(null)
    setDocument(null)
    resetAnalysisState()

    try {
      const uploadedDocument = await uploadDocument(file)
      setDocument(uploadedDocument)
      resetAnalysisState()
      setStatus('success')
    } catch (error) {
      setStatus('error')
      setErrorMessage(getUploadErrorMessage(error))
    }
  }

  async function handleAnalysisStart() {
    if (
      document === null ||
      document.document_id.trim().length === 0 ||
      document.clauses.length === 0 ||
      isAnalysisBusy
    ) {
      return
    }

    setIsCreatingAnalysis(true)
    setAnalysisJob(null)
    setAnalysisRequestError(null)
    setAnalysisRefreshError(null)
    resetResultsState()

    try {
      const job = await createAnalysisJob(document.document_id)
      setAnalysisJob(job)
      if (job.status !== 'completed') resetResultsState()
    } catch (error) {
      setAnalysisRequestError(getAnalysisRequestErrorMessage(error))
    } finally {
      setIsCreatingAnalysis(false)
    }
  }

  async function handleAnalysisRefresh() {
    if (
      document === null ||
      analysisJob === null ||
      !['queued', 'processing'].includes(analysisJob.status) ||
      isAnalysisBusy
    ) {
      return
    }

    setIsRefreshingAnalysis(true)
    setAnalysisRefreshError(null)

    try {
      const job = await getAnalysisJob(
        analysisJob.job_id,
        document.document_id,
      )
      setAnalysisJob(job)
      if (job.status !== 'completed') resetResultsState()
    } catch (error) {
      setAnalysisRefreshError(getAnalysisRefreshErrorMessage(error))
    } finally {
      setIsRefreshingAnalysis(false)
    }
  }

  async function handleViewResults() {
    if (
      document === null ||
      analysisJob?.status !== 'completed' ||
      isAnalysisBusy
    ) return

    setIsLoadingResults(true)
    setAnalysisResults(null)
    setAnalysisResultsError(null)
    try {
      const response = await getAnalysisResults(
        document.document_id,
        analysisJob.job_id,
      )
      if (response.status !== 'completed') {
        throw new Error('Results are not completed.')
      }
      try {
        setAnalysisResults(linkAnalysisResults(document.clauses, response.items))
      } catch {
        setAnalysisResultsError(ANALYSIS_LINK_ERROR_MESSAGE)
      }
    } catch (error) {
      setAnalysisResultsError(getAnalysisResultsErrorMessage(error))
    } finally {
      setIsLoadingResults(false)
    }
  }

  return (
    <main className="container py-5" aria-busy={status === 'uploading'}>
      <header className="mb-4">
        <div className="d-flex align-items-center gap-3 mb-3">
          <img src={brandMark} width="48" height="48" alt="" />
          <p className="text-uppercase text-primary fw-semibold mb-0">
            ContractCheck AI
          </p>
        </div>
        <h1 className="display-6 fw-bold">TXT 문서 업로드와 조항 확인</h1>
        <p className="lead text-secondary mb-0">
          현재 기술 검증 단계에서는 UTF-8 TXT 파일 한 개를 최대 1MB까지
          업로드하고 분리된 조항과 합성 분석 결과를 확인할 수 있습니다.
        </p>
      </header>

      <DocumentUploadForm
        selectedFile={selectedFile}
        isUploading={status === 'uploading'}
        isDisabled={isAnalysisBusy}
        onFileChange={handleFileChange}
        onSubmit={handleUpload}
      />

      <div className="mt-3" aria-live="polite">
        {status === 'uploading' && (
          <p className="alert alert-info mb-0">문서를 업로드하고 있습니다.</p>
        )}
        {errorMessage && (
          <p className="alert alert-danger mb-0" role="alert">
            {errorMessage}
          </p>
        )}
      </div>

      {document && (
        <div className="results-layout mt-4">
          <DocumentSummary document={document} />
          <AnalysisJobPanel
            canStart={
              document.document_id.trim().length > 0 &&
              document.clauses.length > 0
            }
            isCreating={isCreatingAnalysis}
            isRefreshing={isRefreshingAnalysis}
            isLoadingResults={isLoadingResults}
            job={analysisJob}
            requestError={analysisRequestError}
            refreshError={analysisRefreshError}
            onStart={handleAnalysisStart}
            onRefresh={handleAnalysisRefresh}
            onViewResults={handleViewResults}
          />
          <AnalysisResultsPanel
            isLoading={isLoadingResults}
            results={analysisResults}
            error={analysisResultsError}
          />
          <UnclassifiedSections sections={document.unclassified_sections} />
          <ClauseList clauses={document.clauses} />
        </div>
      )}
    </main>
  )
}
