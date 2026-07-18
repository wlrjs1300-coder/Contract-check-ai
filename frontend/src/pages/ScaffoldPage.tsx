import { useState } from 'react'
import { uploadDocument } from '../api/documents'
import { ClauseList } from '../components/ClauseList'
import { DocumentSummary } from '../components/DocumentSummary'
import { DocumentUploadForm } from '../components/DocumentUploadForm'
import { UnclassifiedSections } from '../components/UnclassifiedSections'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import brandMark from '../assets/brand-mark.svg'
import type { UploadedDocument } from '../types/documents'
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

  function handleFileChange(file: File | null) {
    setSelectedFile(file)
    setStatus(file ? 'selected' : 'idle')
    setErrorMessage(null)
    setDocument(null)
  }

  async function handleUpload() {
    if (status === 'uploading') {
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

    try {
      const uploadedDocument = await uploadDocument(file)
      setDocument(uploadedDocument)
      setStatus('success')
    } catch (error) {
      setStatus('error')
      setErrorMessage(getUploadErrorMessage(error))
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
          업로드하고 분리된 조항을 확인할 수 있습니다. 분석 결과는 아직
          제공하지 않습니다.
        </p>
      </header>

      <DocumentUploadForm
        selectedFile={selectedFile}
        isUploading={status === 'uploading'}
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
          <UnclassifiedSections sections={document.unclassified_sections} />
          <ClauseList clauses={document.clauses} />
        </div>
      )}
    </main>
  )
}
