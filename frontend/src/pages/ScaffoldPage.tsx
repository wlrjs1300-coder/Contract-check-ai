import { useState } from 'react'
import { createAnalysisJob, getAnalysisJob } from '../api/analysisJobs'
import { getAnalysisResults } from '../api/analysisResults'
import { uploadDocument } from '../api/documents'
import { AppFrame } from '../components/AppFrame'
import type { AppPage } from '../components/TopNavigation'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import type { UploadedDocument } from '../types/documents'
import type { AnalysisJob } from '../types/analysisJobs'
import type { LinkedAnalysisResult } from '../utils/analysisResult'
import { AnalyzePage } from './AnalyzePage'
import { HomePage } from './HomePage'
import { ResultsPage } from './ResultsPage'
import {
  ANALYSIS_LINK_ERROR_MESSAGE,
  getAnalysisResultsErrorMessage,
  linkAnalysisResults,
} from '../utils/analysisResult'
import {
  getAnalysisRefreshErrorMessage,
  getAnalysisRequestErrorMessage,
} from '../utils/analysisJob'
import { getUploadErrorMessage, validateUploadFile } from '../utils/documentUpload'

type UploadStatus = 'idle' | 'selected' | 'uploading' | 'success' | 'error'

export function ScaffoldPage() {
  useDocumentTitle('ContractCheck AI')
  const [page, setPage] = useState<AppPage>('home')
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
    setPage('analyze')
    setSelectedFile(file)
    setStatus(file ? 'selected' : 'idle')
    setErrorMessage(null)
    setDocument(null)
    resetAnalysisState()
  }

  async function handleUpload() {
    if (status === 'uploading' || isAnalysisBusy) return
    const file = selectedFile
    const validationMessage = validateUploadFile(file)
    if (validationMessage) {
      setStatus('error')
      setErrorMessage(validationMessage)
      return
    }
    if (file === null) return
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
    if (document === null || document.document_id.trim().length === 0 || document.clauses.length === 0 || isAnalysisBusy) return
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
    if (document === null || analysisJob === null || !['queued', 'processing'].includes(analysisJob.status) || isAnalysisBusy) return
    setIsRefreshingAnalysis(true)
    setAnalysisRefreshError(null)
    try {
      const job = await getAnalysisJob(analysisJob.job_id, document.document_id)
      setAnalysisJob(job)
      if (job.status !== 'completed') resetResultsState()
    } catch (error) {
      setAnalysisRefreshError(getAnalysisRefreshErrorMessage(error))
    } finally {
      setIsRefreshingAnalysis(false)
    }
  }

  async function handleViewResults() {
    if (document === null || analysisJob?.status !== 'completed' || isAnalysisBusy) return
    setIsLoadingResults(true)
    setAnalysisResults(null)
    setAnalysisResultsError(null)
    try {
      const response = await getAnalysisResults(document.document_id, analysisJob.job_id)
      if (response.status !== 'completed') throw new Error('Results are not completed.')
      try {
        const linkedResults = linkAnalysisResults(document.clauses, response.items)
        setAnalysisResults(linkedResults)
        setPage('results')
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
    <AppFrame currentPage={page} onNavigate={setPage}>
      {page === 'home' && <HomePage onNavigate={setPage} />}
      {page === 'analyze' && (
        <AnalyzePage
          selectedFile={selectedFile}
          uploadStatus={status}
          uploadError={errorMessage}
          document={document}
          job={analysisJob}
          isCreating={isCreatingAnalysis}
          isRefreshing={isRefreshingAnalysis}
          isLoadingResults={isLoadingResults}
          requestError={analysisRequestError}
          refreshError={analysisRefreshError}
          resultsError={analysisResultsError}
          hasResults={analysisResults !== null}
          onFileChange={handleFileChange}
          onUpload={handleUpload}
          onStart={handleAnalysisStart}
          onRefresh={handleAnalysisRefresh}
          onViewResults={handleViewResults}
        />
      )}
      {page === 'results' && (
        <ResultsPage document={document} results={analysisResults} error={analysisResultsError} onNavigate={setPage} />
      )}
    </AppFrame>
  )
}
