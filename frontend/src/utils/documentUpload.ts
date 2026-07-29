import { ApiError } from '../api/http'

export const MAX_UPLOAD_SIZE_BYTES = 1 * 1024 * 1024

const SERVER_ERROR_MESSAGES: Readonly<Record<string, string>> = {
  'Only .txt files are allowed.': 'TXT 파일만 업로드할 수 있습니다.',
  'The uploaded file is empty.': '내용이 없는 파일은 업로드할 수 없습니다.',
  'The uploaded file exceeds the 1 MB limit.':
    '파일 크기는 1MB 이하여야 합니다.',
  'The uploaded file must be UTF-8 encoded.':
    'UTF-8 형식의 TXT 파일을 선택해 주세요.',
}

export function validateUploadFile(file: File | null): string | null {
  if (file === null) {
    return '파일을 선택해 주세요.'
  }

  if (!/^.+\.txt$/i.test(file.name)) {
    return 'TXT 파일만 업로드할 수 있습니다.'
  }

  if (file.size === 0) {
    return '내용이 없는 파일은 업로드할 수 없습니다.'
  }

  if (file.size > MAX_UPLOAD_SIZE_BYTES) {
    return '파일 크기는 1MB 이하여야 합니다.'
  }

  return null
}

export function getUploadErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.kind === 'network') {
      return '서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.'
    }

    if (error.detail && SERVER_ERROR_MESSAGES[error.detail]) {
      return SERVER_ERROR_MESSAGES[error.detail]
    }
  }

  return '업로드를 완료하지 못했습니다. 파일을 확인한 뒤 다시 시도해 주세요.'
}

export function formatFileSize(sizeBytes: number): string {
  if (sizeBytes < 1024) {
    return `${sizeBytes.toLocaleString('ko-KR')} bytes`
  }

  return `${(sizeBytes / 1024).toFixed(1)} KB`
}
