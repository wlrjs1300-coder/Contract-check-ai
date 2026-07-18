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
    <section className="card border-0 shadow-sm" aria-labelledby="upload-title">
      <div className="card-body p-4">
        <h2 id="upload-title" className="h4">
          TXT 파일 선택
        </h2>
        <p className="text-secondary">
          브라우저 사전 확인 후 파일을 백엔드에 업로드합니다. 최종 형식과
          인코딩 검증은 서버에서 수행합니다.
        </p>

        <form onSubmit={handleSubmit} aria-busy={isUploading}>
          <label htmlFor="document-file" className="form-label fw-semibold">
            계약 문서
          </label>
          <input
            id="document-file"
            className="form-control"
            type="file"
            accept=".txt,text/plain"
            disabled={isUploading || isDisabled}
            onChange={(event) =>
              onFileChange(event.currentTarget.files?.[0] ?? null)
            }
          />

          {selectedFile && (
            <dl className="selected-file mt-3 mb-0">
              <div>
                <dt>파일명</dt>
                <dd>{selectedFile.name}</dd>
              </div>
              <div>
                <dt>파일 크기</dt>
                <dd>{formatFileSize(selectedFile.size)}</dd>
              </div>
            </dl>
          )}

          <button
            type="submit"
            className="btn btn-primary mt-4"
            disabled={isUploading || isDisabled}
          >
            {isUploading ? '업로드 중…' : '문서 업로드'}
          </button>
        </form>
      </div>
    </section>
  )
}
