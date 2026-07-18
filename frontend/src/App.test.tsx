import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type { AnalysisJobStatus } from './types/analysisJobs'
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

function analysisJob(status: AnalysisJobStatus) {
  return {
    job_id: 'job-test',
    document_id: successfulDocument.document_id,
    status,
  }
}

function analysisResults(displayLabel = '추가 확인', recommended = false) {
  return {
    document_id: successfulDocument.document_id,
    job_id: 'job-test',
    status: 'completed',
    items: [
      {
        clause_id: 'clause-001',
        reference_id: 'document-test:clause:1',
        display_label: displayLabel,
        summary: '합성 결과 <strong>강조하지 않음</strong>\n두 번째 줄',
        expert_review_recommended: recommended,
      },
    ],
  }
}

async function uploadSuccessfulDocument() {
  selectFile(new File(['제1조 합성 본문'], 'sample.txt'))
  fireEvent.click(screen.getByRole('button', { name: '문서 업로드' }))
  await screen.findByRole('heading', { name: '업로드 결과' })
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
    expect(screen.getByText(/합성 분석 결과를 확인할 수 있습니다/)).toBeInTheDocument()
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

describe('analysis job flow', () => {
  it('does not show analysis controls before a successful upload', () => {
    render(<App />)

    expect(screen.queryByRole('button', { name: '분석 시작' })).not.toBeInTheDocument()
  })

  it('blocks analysis when the uploaded document has no clauses', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ ...successfulDocument, clause_count: 0, clauses: [] }),
    )
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)

    await uploadSuccessfulDocument()

    expect(screen.getByRole('button', { name: '분석 시작' })).toBeDisabled()
    expect(screen.getByText(/분리된 조항이 없어 분석을 시작할 수 없습니다/)).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it('creates an analysis job and renders completed without fetching results', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(successfulDocument))
      .mockResolvedValueOnce(jsonResponse(analysisJob('completed')))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)

    await uploadSuccessfulDocument()
    fireEvent.click(screen.getByRole('button', { name: '분석 시작' }))

    expect(await screen.findByText('분석 작업이 완료되었습니다.')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'http://localhost:8000/documents/document-test/analysis-jobs',
      { method: 'POST' },
    )
    expect(
      fetchMock.mock.calls.some(([url]) => String(url).includes('analysis-results')),
    ).toBe(false)
  })

  it('prevents duplicate analysis and document changes while creating', async () => {
    let resolveAnalysis: ((response: Response) => void) | undefined
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(successfulDocument))
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            resolveAnalysis = resolve
          }),
      )
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)

    await uploadSuccessfulDocument()
    fireEvent.click(screen.getByRole('button', { name: '분석 시작' }))

    const creatingButton = screen.getByRole('button', { name: '분석 요청 중…' })
    expect(creatingButton).toBeDisabled()
    expect(screen.getByLabelText('계약 문서')).toBeDisabled()
    expect(screen.getByRole('button', { name: '문서 업로드' })).toBeDisabled()
    fireEvent.click(creatingButton)
    expect(fetchMock).toHaveBeenCalledTimes(2)

    resolveAnalysis?.(jsonResponse(analysisJob('completed')))
    await screen.findByText('분석 작업이 완료되었습니다.')
  })

  it.each<[AnalysisJobStatus, string]>([
    ['queued', '분석 작업이 대기 중입니다.'],
    ['processing', '분석 작업을 처리 중입니다.'],
    ['failed', '분석 작업을 완료하지 못했습니다. 다시 시도해 주세요.'],
  ])('renders the %s response state', async (status, message) => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(successfulDocument))
      .mockResolvedValueOnce(jsonResponse(analysisJob(status)))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)

    await uploadSuccessfulDocument()
    fireEvent.click(screen.getByRole('button', { name: '분석 시작' }))

    expect(await screen.findByText(message)).toBeInTheDocument()
  })

  it('refreshes a queued job once and applies completed', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(successfulDocument))
      .mockResolvedValueOnce(jsonResponse(analysisJob('queued')))
      .mockResolvedValueOnce(jsonResponse(analysisJob('completed')))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)

    await uploadSuccessfulDocument()
    fireEvent.click(screen.getByRole('button', { name: '분석 시작' }))
    await screen.findByText('분석 작업이 대기 중입니다.')
    fireEvent.click(screen.getByRole('button', { name: '상태 다시 확인' }))

    expect(await screen.findByText('분석 작업이 완료되었습니다.')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      'http://localhost:8000/analysis-jobs/job-test',
      { method: 'GET' },
    )
  })

  it('prevents duplicate status lookups and document changes while refreshing', async () => {
    let resolveRefresh: ((response: Response) => void) | undefined
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(successfulDocument))
      .mockResolvedValueOnce(jsonResponse(analysisJob('processing')))
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            resolveRefresh = resolve
          }),
      )
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)

    await uploadSuccessfulDocument()
    fireEvent.click(screen.getByRole('button', { name: '분석 시작' }))
    await screen.findByText('분석 작업을 처리 중입니다.')
    fireEvent.click(screen.getByRole('button', { name: '상태 다시 확인' }))

    const refreshButton = screen.getByRole('button', { name: '상태 확인 중…' })
    expect(refreshButton).toBeDisabled()
    expect(screen.getByLabelText('계약 문서')).toBeDisabled()
    fireEvent.click(refreshButton)
    expect(fetchMock).toHaveBeenCalledTimes(3)

    resolveRefresh?.(jsonResponse(analysisJob('failed')))
    await screen.findByText('분석 작업을 완료하지 못했습니다. 다시 시도해 주세요.')
  })

  it('keeps job status separate when a status lookup fails', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(successfulDocument))
      .mockResolvedValueOnce(jsonResponse(analysisJob('queued')))
      .mockResolvedValueOnce(new Response('failure', { status: 500 }))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)

    await uploadSuccessfulDocument()
    fireEvent.click(screen.getByRole('button', { name: '분석 시작' }))
    await screen.findByText('분석 작업이 대기 중입니다.')
    fireEvent.click(screen.getByRole('button', { name: '상태 다시 확인' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      '분석 상태를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.',
    )
    expect(screen.getByText('분석 작업이 대기 중입니다.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '상태 다시 확인' })).toBeEnabled()
  })

  it.each([
    [
      () => Promise.resolve(new Response('failure', { status: 500 })),
      '분석 요청을 완료하지 못했습니다. 잠시 후 다시 시도해 주세요.',
    ],
    [
      () => Promise.reject(new TypeError('network unavailable')),
      '서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.',
    ],
    [
      () => Promise.resolve(jsonResponse({ job_id: '' })),
      '분석 요청을 완료하지 못했습니다. 잠시 후 다시 시도해 주세요.',
    ],
  ])('renders a safe analysis request error', async (analysisResponse, message) => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(successfulDocument))
      .mockImplementationOnce(analysisResponse)
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)

    await uploadSuccessfulDocument()
    fireEvent.click(screen.getByRole('button', { name: '분석 시작' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(screen.getByRole('button', { name: '분석 시작' })).toBeEnabled()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('clears the previous analysis state when a new file is selected', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(successfulDocument))
      .mockResolvedValueOnce(jsonResponse(analysisJob('completed')))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)

    await uploadSuccessfulDocument()
    fireEvent.click(screen.getByRole('button', { name: '분석 시작' }))
    await screen.findByText('분석 작업이 완료되었습니다.')

    selectFile(new File(['제1조 새 합성 본문'], 'next.txt'))

    expect(screen.queryByText('분석 작업이 완료되었습니다.')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '분석 작업 상태' })).not.toBeInTheDocument()
  })
})

describe('analysis results flow', () => {
  async function completeAnalysis(fetchMock: ReturnType<typeof vi.fn>) {
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    await uploadSuccessfulDocument()
    fireEvent.click(screen.getByRole('button', { name: '분석 시작' }))
    await screen.findByText('분석 작업이 완료되었습니다.')
  }

  it('shows the result action only after completion and renders safe text', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(successfulDocument))
      .mockResolvedValueOnce(jsonResponse(analysisJob('completed')))
      .mockResolvedValueOnce(jsonResponse(analysisResults('위험', true)))
    await completeAnalysis(fetchMock)

    fireEvent.click(screen.getByRole('button', { name: '분석 결과 보기' }))
    expect(await screen.findByRole('heading', { name: '분석 결과' })).toBeInTheDocument()
    expect(screen.getByText('위험')).toBeInTheDocument()
    expect(screen.getByText('합성 결과 <strong>강조하지 않음</strong>', { exact: false })).toBeInTheDocument()
    expect(document.querySelector('strong')?.textContent).not.toBe('강조하지 않음')
    expect(screen.getByText('전문가 검토를 권고합니다.')).toBeInTheDocument()
    expect(screen.getAllByText('목적')).toHaveLength(2)
    expect(screen.getAllByText('제1조').length).toBeGreaterThan(0)
    expect(screen.queryByText('document-test')).not.toBeInTheDocument()
    expect(screen.queryByText('hash-not-shown')).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      'http://localhost:8000/documents/document-test/analysis-results',
      { method: 'GET' },
    )
  })

  it.each(['안전', '주의', '위험', '추가 확인'])(
    'renders the original %s label',
    async (label) => {
      const fetchMock = vi.fn()
        .mockResolvedValueOnce(jsonResponse(successfulDocument))
        .mockResolvedValueOnce(jsonResponse(analysisJob('completed')))
        .mockResolvedValueOnce(jsonResponse(analysisResults(label)))
      await completeAnalysis(fetchMock)
      fireEvent.click(screen.getByRole('button', { name: '분석 결과 보기' }))
      expect(await screen.findByText(label)).toBeInTheDocument()
      expect(await screen.findByText('별도 권고가 표시되지 않았습니다.')).toBeInTheDocument()
      expect(screen.queryByText(/검토 불필요/)).not.toBeInTheDocument()
    },
  )

  it('blocks duplicate and conflicting actions while loading results', async () => {
    let resolveResults: ((response: Response) => void) | undefined
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(successfulDocument))
      .mockResolvedValueOnce(jsonResponse(analysisJob('completed')))
      .mockImplementationOnce(() => new Promise<Response>((resolve) => { resolveResults = resolve }))
    await completeAnalysis(fetchMock)
    fireEvent.click(screen.getByRole('button', { name: '분석 결과 보기' }))

    const loadingButton = screen.getByRole('button', { name: '결과 불러오는 중…' })
    expect(loadingButton).toBeDisabled()
    expect(screen.getByLabelText('계약 문서')).toBeDisabled()
    expect(screen.getByRole('button', { name: '문서 업로드' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '분석 시작' })).toBeDisabled()
    fireEvent.click(loadingButton)
    expect(fetchMock).toHaveBeenCalledTimes(3)
    resolveResults?.(jsonResponse(analysisResults()))
    await screen.findByText('별도 권고가 표시되지 않았습니다.')
  })

  it.each([
    [jsonResponse({ detail: 'Analysis result not found.' }, 404), '저장된 분석 결과를 찾지 못했습니다.'],
    [new Response('failure', { status: 500 }), '분석 결과를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.'],
    [jsonResponse({ ...analysisResults(), job_id: 'other' }), '분석 결과를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.'],
  ])('shows a safe result error', async (response, message) => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(successfulDocument))
      .mockResolvedValueOnce(jsonResponse(analysisJob('completed')))
      .mockResolvedValueOnce(response)
    await completeAnalysis(fetchMock)
    fireEvent.click(screen.getByRole('button', { name: '분석 결과 보기' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(message)
  })

  it('shows linkage failure separately and clears results for a new file', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(successfulDocument))
      .mockResolvedValueOnce(jsonResponse(analysisJob('completed')))
      .mockResolvedValueOnce(jsonResponse({
        ...analysisResults(),
        items: [{ ...analysisResults().items[0], reference_id: 'other' }],
      }))
    await completeAnalysis(fetchMock)
    fireEvent.click(screen.getByRole('button', { name: '분석 결과 보기' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('분석 결과와 문서 조항을 연결하지 못했습니다')

    selectFile(new File(['제1조 새 합성 본문'], 'next.txt'))
    expect(screen.queryByRole('heading', { name: '분석 결과' })).not.toBeInTheDocument()
  })

  it('shows network failure without an actual request', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(successfulDocument))
      .mockResolvedValueOnce(jsonResponse(analysisJob('completed')))
      .mockRejectedValueOnce(new TypeError('unavailable'))
    await completeAnalysis(fetchMock)
    fireEvent.click(screen.getByRole('button', { name: '분석 결과 보기' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('서버에 연결하지 못했습니다')
  })
})
