import type { FormEvent } from 'react'
import { formatFileSize } from '../utils/documentUpload'

type DocumentUploadFormProps = Readonly<{
  selectedFile: File | null
  isUploading: boolean
  isDisabled?: boolean
  onFileChange: (file: File | null) => void
  onSubmit: () => void
}>

export function DocumentUploadForm({
  selectedFile,
  isUploading,
  isDisabled = false,
  onFileChange,
  onSubmit,
}: DocumentUploadFormProps) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    onSubmit()
  }

  return (
    <section className="card upload-panel" aria-labelledby="upload-title">
      <div className="card-body">
        <div className="upload-heading">
          <div>
            <h2 id="upload-title" className="h4">TXT 파일 선택</h2>
            <p className="text-secondary">분석할 계약 문서 한 개를 선택해 주세요.</p>
          </div>
          <button
            type="button"
            className="upload-reset"
            aria-label="선택 초기화"
            title="선택 초기화"
            disabled={selectedFile === null || isUploading || isDisabled}
            onClick={() => onFileChange(null)}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M4.5 8.5V4.5h4" /><path d="M5 8a8 8 0 1 1-1 6" /><path d="m4.5 4.5 4 4" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} aria-busy={isUploading}>
          <label htmlFor="document-file" className="file-select-label">
            <span aria-hidden="true">＋</span>
            <strong>계약 문서</strong>
            <small>UTF-8 TXT · 최대 1MB</small>
          </label>
          <input
            id="document-file"
            className="visually-hidden"
            type="file"
            aria-label="계약 문서"
            accept=".txt,text/plain"
            disabled={isUploading || isDisabled}
            onChange={(event) =>
              onFileChange(event.currentTarget.files?.[0] ?? null)
            }
          />

          {selectedFile && (
            <div className="selected-file-area">
              <dl className="selected-file mb-0">
                <div><dt>파일명</dt><dd>{selectedFile.name}</dd></div>
                <div><dt>파일 크기</dt><dd>{formatFileSize(selectedFile.size)}</dd></div>
              </dl>
              <button
                type="submit"
                className="btn btn-primary upload-action"
                disabled={isUploading || isDisabled}
              >
                {isUploading ? '업로드 중…' : '문서 업로드'}
              </button>
            </div>
          )}
        </form>
      </div>
    </section>
  )
}
