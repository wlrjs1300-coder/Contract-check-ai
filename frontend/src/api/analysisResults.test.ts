import { describe, expect, it, vi } from 'vitest'
import { getAnalysisResults } from './analysisResults'

const validItem = {
  clause_id: 'clause-001',
  reference_id: 'document-test:clause:1',
  display_label: '추가 확인',
  summary: '합성 분석 결과입니다.',
  expert_review_recommended: false,
}
const validResults = {
  document_id: 'document-test',
  job_id: 'job-test',
  status: 'completed',
  items: [validItem],
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), { status })
}

describe('analysis results API', () => {
  it('gets results using an encoded path without a body or headers', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      jsonResponse({ ...validResults, document_id: 'document/id?' }),
    )
    await getAnalysisResults('document/id?', 'job-test', fetcher)
    expect(fetcher).toHaveBeenCalledWith(
      'http://localhost:8000/documents/document%2Fid%3F/analysis-results',
      { method: 'GET' },
    )
    const [, options] = fetcher.mock.calls[0]
    expect(options.body).toBeUndefined()
    expect(options.headers).toBeUndefined()
  })

  it.each(['queued', 'processing', 'completed', 'failed'])(
    'accepts the %s status contract',
    async (status) => {
      const fetcher = vi.fn().mockResolvedValue(jsonResponse({ ...validResults, status }))
      await expect(getAnalysisResults('document-test', 'job-test', fetcher)).resolves.toMatchObject({ status })
    },
  )

  it.each(['안전', '주의', '위험', '추가 확인'])(
    'accepts the %s display label',
    async (displayLabel) => {
      const fetcher = vi.fn().mockResolvedValue(jsonResponse({
        ...validResults,
        items: [{ ...validItem, display_label: displayLabel }],
      }))
      await expect(getAnalysisResults('document-test', 'job-test', fetcher)).resolves.toBeDefined()
    },
  )

  it.each([
    ['empty job id', { ...validResults, job_id: '' }],
    ['document mismatch', { ...validResults, document_id: 'other' }],
    ['job mismatch', { ...validResults, job_id: 'other' }],
    ['invalid status', { ...validResults, status: 'unknown' }],
    ['empty clause id', { ...validResults, items: [{ ...validItem, clause_id: '' }] }],
    ['empty reference id', { ...validResults, items: [{ ...validItem, reference_id: '' }] }],
    ['invalid label', { ...validResults, items: [{ ...validItem, display_label: '고위험' }] }],
    ['invalid summary', { ...validResults, items: [{ ...validItem, summary: 1 }] }],
    ['invalid recommendation', { ...validResults, items: [{ ...validItem, expert_review_recommended: 'yes' }] }],
    ['unexpected shape', { document_id: 'document-test' }],
  ])('rejects $s', async (_reason, payload) => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse(payload))
    await expect(getAnalysisResults('document-test', 'job-test', fetcher)).rejects.toMatchObject({ kind: 'invalid-response' })
  })

  it.each(['clause_id', 'reference_id'] as const)(
    'rejects duplicate %s values',
    async (key) => {
      const fetcher = vi.fn().mockResolvedValue(jsonResponse({
        ...validResults,
        items: [validItem, { ...validItem, [key]: validItem[key], summary: '두 번째 합성 결과' }],
      }))
      await expect(getAnalysisResults('document-test', 'job-test', fetcher)).rejects.toMatchObject({ kind: 'invalid-response' })
    },
  )

  it('rejects an empty request identifier before fetching', async () => {
    const fetcher = vi.fn()
    await expect(getAnalysisResults('', 'job-test', fetcher)).rejects.toMatchObject({ kind: 'invalid-response' })
    expect(fetcher).not.toHaveBeenCalled()
  })

  it('preserves JSON detail for HTTP errors', async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse({ detail: 'Analysis result not found.' }, 404))
    await expect(getAnalysisResults('document-test', 'job-test', fetcher)).rejects.toMatchObject({ kind: 'http', status: 404, detail: 'Analysis result not found.' })
  })

  it('distinguishes non-JSON HTTP and network errors', async () => {
    const httpFetcher = vi.fn().mockResolvedValue(new Response('failure', { status: 500 }))
    await expect(getAnalysisResults('document-test', 'job-test', httpFetcher)).rejects.toMatchObject({ kind: 'http', detail: null })
    const networkFetcher = vi.fn().mockRejectedValue(new TypeError('unavailable'))
    await expect(getAnalysisResults('document-test', 'job-test', networkFetcher)).rejects.toMatchObject({ kind: 'network' })
  })
})
