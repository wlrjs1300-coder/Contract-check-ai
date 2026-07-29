import { describe, expect, it } from 'vitest'
import { MAX_UPLOAD_SIZE_BYTES, validateUploadFile } from './documentUpload'

describe('validateUploadFile', () => {
  it('requires a file', () => {
    expect(validateUploadFile(null)).toBe('파일을 선택해 주세요.')
  })

  it('allows lowercase and uppercase TXT extensions', () => {
    expect(validateUploadFile(new File(['x'], 'sample.txt'))).toBeNull()
    expect(validateUploadFile(new File(['x'], 'sample.TXT'))).toBeNull()
  })

  it('rejects another extension', () => {
    expect(validateUploadFile(new File(['x'], 'sample.pdf'))).toBe(
      'TXT 파일만 업로드할 수 있습니다.',
    )
    expect(validateUploadFile(new File(['x'], '.txt'))).toBe(
      'TXT 파일만 업로드할 수 있습니다.',
    )
  })

  it('rejects an empty TXT file', () => {
    expect(validateUploadFile(new File([], 'empty.txt'))).toBe(
      '내용이 없는 파일은 업로드할 수 없습니다.',
    )
  })

  it('allows the exact size limit and rejects one byte more', () => {
    expect(
      validateUploadFile(
        new File([new Uint8Array(MAX_UPLOAD_SIZE_BYTES)], 'limit.txt'),
      ),
    ).toBeNull()
    expect(
      validateUploadFile(
        new File([new Uint8Array(MAX_UPLOAD_SIZE_BYTES + 1)], 'large.txt'),
      ),
    ).toBe('파일 크기는 1MB 이하여야 합니다.')
  })
})
