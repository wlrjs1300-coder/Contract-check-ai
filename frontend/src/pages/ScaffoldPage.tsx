import { useEffect, useRef, useState } from 'react'
import { getCurrentUser, login, register } from '../api/auth'
import { ApiError } from '../api/http'
import { clearAccessToken, readAccessToken, storeAccessToken } from '../auth/session'
import { createAnalysisJob, getAnalysisJob } from '../api/analysisJobs'
import { getAnalysisResults } from '../api/analysisResults'
import { uploadDocument } from '../api/documents'
import { AppFrame } from '../components/AppFrame'
import { AuthDialog, type AuthMode } from '../components/AuthDialog'
import type { AppPage } from '../components/TopNavigation'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import type { UploadedDocument } from '../types/documents'
import type { AnalysisJob } from '../types/analysisJobs'
import type { AuthStatus, AuthUser } from '../types/auth'
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
  const [initialToken] = useState(readAccessToken)
  const sessionCheckStarted = useRef(false)
  const [authStatus, setAuthStatus] = useState<AuthStatus>(initialToken ? 'checking' : 'anonymous')
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null)
  const [authMode, setAuthMode] = useState<AuthMode | null>(null)
  const [authNotice, setAuthNotice] = useState<string | null>(null)
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

  useEffect(() => {
    const token = initialToken
    if (token === null || sessionCheckStarted.current) return
    sessionCheckStarted.current = true
    void getCurrentUser(token).then((user) => {
      setCurrentUser(user)
      setAuthStatus('authenticated')
    }).catch(() => {
      clearAccessToken()
      setCurrentUser(null)
      setAuthStatus('anonymous')
    })
  }, [initialToken])

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

  function resetProtectedState() {
    setDocument(null)
    setStatus(selectedFile ? 'selected' : 'idle')
    setErrorMessage(null)
    resetAnalysisState()
  }

  function expireSession() {
    clearAccessToken()
    setCurrentUser(null)
    setAuthStatus('anonymous')
    resetProtectedState()
    setAuthNotice('로그인 정보가 만료되었습니다. 다시 로그인해 주세요.')
    setAuthMode('login')
  }

  function requireAccessToken(): string | null {
    const token = authStatus === 'authenticated' ? readAccessToken() : null
    if (token) return token
    setAuthNotice(null)
    setAuthMode('login')
    return null
  }

  function handleProtectedError(error: unknown): boolean {
    if (error instanceof ApiError && error.status === 401) {
      expireSession()
      return true
    }
    return false
  }

  async function handleLogin(email: string, password: string) {
    const response = await login(email, password)
    storeAccessToken(response.access_token)
    try {
      const user = await getCurrentUser(response.access_token)
      setCurrentUser(user)
      setAuthStatus('authenticated')
      setAuthNotice(null)
      setAuthMode(null)
    } catch (error) {
      clearAccessToken()
      setCurrentUser(null)
      setAuthStatus('anonymous')
      throw error
    }
  }

  async function handleRegister(email: string, password: string) {
    await register(email, password)
    setAuthNotice('회원가입이 완료되었습니다. 로그인해 주세요.')
    setAuthMode('login')
  }

  function handleLogout() {
    clearAccessToken()
    setCurrentUser(null)
    setAuthStatus('anonymous')
    setAuthNotice(null)
    resetProtectedState()
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
    const accessToken = requireAccessToken()
    if (accessToken === null) return
    setStatus('uploading')
    setErrorMessage(null)
    setDocument(null)
    resetAnalysisState()
    try {
      const uploadedDocument = await uploadDocument(file, accessToken)
      setDocument(uploadedDocument)
      resetAnalysisState()
      setStatus('success')
    } catch (error) {
      if (handleProtectedError(error)) return
      setStatus('error')
      setErrorMessage(getUploadErrorMessage(error))
    }
  }

  async function handleAnalysisStart() {
    if (document === null || document.document_id.trim().length === 0 || document.clauses.length === 0 || isAnalysisBusy) return
    const accessToken = requireAccessToken()
    if (accessToken === null) return
    setIsCreatingAnalysis(true)
    setAnalysisJob(null)
    setAnalysisRequestError(null)
    setAnalysisRefreshError(null)
    resetResultsState()
    try {
      const job = await createAnalysisJob(document.document_id, accessToken)
      setAnalysisJob(job)
      if (job.status !== 'completed') resetResultsState()
    } catch (error) {
      if (handleProtectedError(error)) return
      setAnalysisRequestError(getAnalysisRequestErrorMessage(error))
    } finally {
      setIsCreatingAnalysis(false)
    }
  }

  async function handleAnalysisRefresh() {
    if (document === null || analysisJob === null || !['queued', 'processing'].includes(analysisJob.status) || isAnalysisBusy) return
    const accessToken = requireAccessToken()
    if (accessToken === null) return
    setIsRefreshingAnalysis(true)
    setAnalysisRefreshError(null)
    try {
      const job = await getAnalysisJob(analysisJob.job_id, document.document_id, accessToken)
      setAnalysisJob(job)
      if (job.status !== 'completed') resetResultsState()
    } catch (error) {
      if (handleProtectedError(error)) return
      setAnalysisRefreshError(getAnalysisRefreshErrorMessage(error))
    } finally {
      setIsRefreshingAnalysis(false)
    }
  }

  async function handleViewResults() {
    if (document === null || analysisJob?.status !== 'completed' || isAnalysisBusy) return
    const accessToken = requireAccessToken()
    if (accessToken === null) return
    setIsLoadingResults(true)
    setAnalysisResults(null)
    setAnalysisResultsError(null)
    try {
      const response = await getAnalysisResults(document.document_id, analysisJob.job_id, accessToken)
      if (response.status !== 'completed') throw new Error('Results are not completed.')
      try {
        const linkedResults = linkAnalysisResults(document.clauses, response.items)
        setAnalysisResults(linkedResults)
        setPage('results')
      } catch {
        setAnalysisResultsError(ANALYSIS_LINK_ERROR_MESSAGE)
      }
    } catch (error) {
      if (handleProtectedError(error)) return
      setAnalysisResultsError(getAnalysisResultsErrorMessage(error))
    } finally {
      setIsLoadingResults(false)
    }
  }

  return (
    <AppFrame currentPage={page} onNavigate={setPage} authStatus={authStatus} currentUser={currentUser} onOpenAuth={(mode) => { setAuthNotice(null); setAuthMode(mode) }} onLogout={handleLogout}>
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
      <AuthDialog key={authMode ?? 'closed'} mode={authMode} notice={authNotice} onClose={() => { setAuthMode(null); setAuthNotice(null) }} onLogin={handleLogin} onRegister={handleRegister} onModeChange={(mode) => { setAuthNotice(null); setAuthMode(mode) }} />
    </AppFrame>
  )
}
