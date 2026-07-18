import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type { UploadedDocument } from './types/documents'

const successfulDocument: UploadedDocument = {
  document_id: 'document-test',
  filename: 'sample.TXT',
  content_type: 'text/plain',
  size_bytes: 42,
  character_count: 21,
  status: 'processed',
  clause_count: 1,
  clauses: [
    {
      clause_id: 'clause-001',
      reference_id: 'document-test:clause:1',
      source_hash: 'hash-not-shown',
      ordinal: 1,
      marker: '제1조',
      clause_type: 'normal',
      title: '목적',
      body: '합성 문서의 목적을 정합니다.',
      warnings: ['empty_body', 'future_warning'],
    },
  ],
  unclassified_sections: ['합성 미분류 안내 문장'],
  document_warnings: ['no_clause_marker_detected'],
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function selectFile(file: File) {
  fireEvent.change(screen.getByLabelText('계약 문서'), {
    target: { files: [file] },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('App', () => {
  it('renders the service name', () => {
    render(<App />)

    expect(screen.getByText('ContractCheck AI')).toBeInTheDocument()
  })

  it('renders the current upload scope', () => {
    render(<App />)

    expect(
      screen.getByRole('heading', { name: 'TXT 문서 업로드와 조항 확인' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/분석 결과는 아직 제공하지 않습니다/)).toBeInTheDocument()
  })

  it('does not request an upload without a selected file', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: '문서 업로드' }))

    expect(screen.getByRole('alert')).toHaveTextContent('파일을 선택해 주세요.')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it.each([
    [new File(['content'], 'sample.pdf'), 'TXT 파일만 업로드할 수 있습니다.'],
    [new File([], 'empty.txt'), '내용이 없는 파일은 업로드할 수 없습니다.'],
    [
      new File([new Uint8Array(1024 * 1024 + 1)], 'large.txt'),
      '파일 크기는 1MB 이하여야 합니다.',
    ],
  ])('blocks an invalid file before upload', (file, message) => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)

    selectFile(file)
    fireEvent.click(screen.getByRole('button', { name: '문서 업로드' }))

    expect(screen.getByRole('alert')).toHaveTextContent(message)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('uploads an uppercase TXT file at the exact size limit', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(successfulDocument))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)

    const file = new File([new Uint8Array(1024 * 1024)], 'sample.TXT', {
      type: 'text/plain',
    })
    selectFile(file)
    fireEvent.click(screen.getByRole('button', { name: '문서 업로드' }))

    await screen.findByRole('heading', { name: '업로드 결과' })
    expect(fetchMock).toHaveBeenCalledOnce()
    expect(screen.getAllByText('sample.TXT')).toHaveLength(2)
  })

  it('disables duplicate submission while uploading', async () => {
    let resolveRequest: ((response: Response) => void) | undefined
    const fetchMock = vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          resolveRequest = resolve
        }),
    )
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)

    selectFile(new File(['제1조 합성 본문'], 'sample.txt'))
    fireEvent.click(screen.getByRole('button', { name: '문서 업로드' }))

    const uploadingButton = screen.getByRole('button', { name: '업로드 중…' })
    expect(uploadingButton).toBeDisabled()
    fireEvent.click(uploadingButton)
    expect(fetchMock).toHaveBeenCalledOnce()

    resolveRequest?.(jsonResponse(successfulDocument))
    await screen.findByRole('heading', { name: '업로드 결과' })
  })

  it('renders metadata, warnings, unclassified text, and clauses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(successfulDocument)))
    render(<App />)

    selectFile(new File(['제1조 합성 본문'], 'sample.txt'))
    fireEvent.click(screen.getByRole('button', { name: '문서 업로드' }))

    await screen.findByRole('heading', { name: '업로드 결과' })
    expect(screen.getByText('21')).toBeInTheDocument()
    expect(screen.getByText('processed')).toBeInTheDocument()
    expect(screen.getByText('인식할 수 있는 조항 표기를 찾지 못했습니다.')).toBeInTheDocument()
    expect(screen.getByText('합성 미분류 안내 문장')).toBeInTheDocument()
    expect(screen.getByText('제1조')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '목적' })).toBeInTheDocument()
    expect(screen.getByText('합성 문서의 목적을 정합니다.')).toBeInTheDocument()
    expect(screen.getByText('조항 본문이 비어 있습니다.')).toBeInTheDocument()
    expect(screen.getByText('future_warning')).toBeInTheDocument()
    expect(screen.queryByText('hash-not-shown')).not.toBeInTheDocument()
  })

  it('renders a successful empty clause state', async () => {
    const emptyDocument = {
      ...successfulDocument,
      clause_count: 0,
      clauses: [],
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(emptyDocument)))
    render(<App />)

    selectFile(new File(['합성 안내'], 'sample.txt'))
    fireEvent.click(screen.getByRole('button', { name: '문서 업로드' }))

    expect(
      await screen.findByText('분리된 조항이 없습니다. 문서 형식과 조항 표기를 확인해 주세요.'),
    ).toBeInTheDocument()
  })

  it.each([
    ['Only .txt files are allowed.', 'TXT 파일만 업로드할 수 있습니다.'],
    ['The uploaded file is empty.', '내용이 없는 파일은 업로드할 수 없습니다.'],
    ['The uploaded file exceeds the 1 MB limit.', '파일 크기는 1MB 이하여야 합니다.'],
    ['The uploaded file must be UTF-8 encoded.', 'UTF-8 형식의 TXT 파일을 선택해 주세요.'],
  ])('maps a server detail to a safe message', async (detail, message) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail }, 400)))
    render(<App />)

    selectFile(new File(['합성 본문'], 'sample.txt'))
    fireEvent.click(screen.getByRole('button', { name: '문서 업로드' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(message)
  })

  it('shows a network failure and allows retry', async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('network unavailable'))
      .mockResolvedValueOnce(jsonResponse(successfulDocument))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)

    selectFile(new File(['합성 본문'], 'sample.txt'))
    fireEvent.click(screen.getByRole('button', { name: '문서 업로드' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      '서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.',
    )

    fireEvent.click(screen.getByRole('button', { name: '문서 업로드' }))
    await screen.findByRole('heading', { name: '업로드 결과' })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('clears previous success and error state when a new file is selected', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(successfulDocument)))
    render(<App />)

    selectFile(new File(['합성 본문'], 'first.txt'))
    fireEvent.click(screen.getByRole('button', { name: '문서 업로드' }))
    await screen.findByRole('heading', { name: '업로드 결과' })

    selectFile(new File(['합성 본문'], 'second.txt'))
    await waitFor(() => {
      expect(screen.queryByRole('heading', { name: '업로드 결과' })).not.toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('계약 문서'), {
      target: { files: [new File([], 'empty.txt')] },
    })
    fireEvent.click(screen.getByRole('button', { name: '문서 업로드' }))
    expect(screen.getByRole('alert')).toBeInTheDocument()

    selectFile(new File(['합성 본문'], 'third.txt'))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
