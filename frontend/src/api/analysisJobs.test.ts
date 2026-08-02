import { describe, expect, it, vi } from 'vitest'
import type { AnalysisJob, AnalysisJobStatus } from '../types/analysisJobs'
import { createAnalysisJob, getAnalysisJob } from './analysisJobs'

const completedJob: AnalysisJob = {
  job_id: 'job-test',
  document_id: 'document-test',
  status: 'completed',
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), { status })
}

describe('analysis job API', () => {
  it('creates a job with an encoded document path, bearer header, and no body', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      jsonResponse({
        ...completedJob,
        document_id: 'document/id?',
      }),
    )

    await expect(createAnalysisJob('document/id?', 'test-token', fetcher)).resolves.toMatchObject({
      status: 'completed',
    })

    expect(fetcher).toHaveBeenCalledWith(
      'http://localhost:8000/documents/document%2Fid%3F/analysis-jobs',
      expect.objectContaining({ method: 'POST', headers: expect.any(Headers) }),
    )
    expect(new Headers(fetcher.mock.calls[0][1]?.headers).get('Authorization')).toBe('Bearer test-token')
    const [, options] = fetcher.mock.calls[0]
    expect(options.body).toBeUndefined()
    expect(new Headers(options.headers).get('Authorization')).toBe('Bearer test-token')
  })

  it.each<AnalysisJobStatus>(['queued', 'processing', 'completed', 'failed'])(
    'accepts the %s status',
    async (status) => {
      const fetcher = vi.fn().mockResolvedValue(jsonResponse({ ...completedJob, status }))

      await expect(createAnalysisJob('document-test', 'test-token', fetcher)).resolves.toMatchObject({
        status,
      })
    },
  )

  it.each([
    { payload: { ...completedJob, status: 'unknown' }, reason: 'invalid status' },
    { payload: { ...completedJob, job_id: '' }, reason: 'empty job id' },
    { payload: { ...completedJob, document_id: '' }, reason: 'empty document id' },
    {
      payload: { ...completedJob, document_id: 'another-document' },
      reason: 'mismatched document id',
    },
    { payload: { document_id: 'document-test' }, reason: 'incomplete response' },
  ])('rejects an invalid response: $reason', async ({ payload }) => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse(payload))

    await expect(createAnalysisJob('document-test', 'test-token', fetcher)).rejects.toMatchObject({
      kind: 'invalid-response',
    })
  })

  it('preserves JSON detail and status from an HTTP error', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      jsonResponse({ detail: 'Document not found.' }, 404),
    )

    await expect(createAnalysisJob('document-test', 'test-token', fetcher)).rejects.toMatchObject({
      kind: 'http',
      status: 404,
      detail: 'Document not found.',
    })
  })

  it('distinguishes a non-JSON HTTP error', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response('failure', { status: 500 }))

    await expect(createAnalysisJob('document-test', 'test-token', fetcher)).rejects.toMatchObject({
      kind: 'http',
      status: 500,
      detail: null,
    })
  })

  it('distinguishes a network failure', async () => {
    const fetcher = vi.fn().mockRejectedValue(new TypeError('network unavailable'))

    await expect(createAnalysisJob('document-test', 'test-token', fetcher)).rejects.toMatchObject({
      kind: 'network',
    })
  })

  it('gets a job with bearer authorization and validates both identifiers', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      jsonResponse({
        job_id: 'job/id?',
        document_id: 'document-test',
        status: 'processing',
      }),
    )

    await expect(
      getAnalysisJob('job/id?', 'document-test', 'test-token', fetcher),
    ).resolves.toMatchObject({ status: 'processing' })
    expect(fetcher).toHaveBeenCalledWith(
      'http://localhost:8000/analysis-jobs/job%2Fid%3F',
      expect.objectContaining({ method: 'GET', headers: expect.any(Headers) }),
    )
    expect(new Headers(fetcher.mock.calls[0][1]?.headers).get('Authorization')).toBe('Bearer test-token')
  })

  it('does not request status without a job id', async () => {
    const fetcher = vi.fn()

    await expect(
      getAnalysisJob('', 'document-test', 'test-token', fetcher),
    ).rejects.toMatchObject({ kind: 'invalid-response' })
    expect(fetcher).not.toHaveBeenCalled()
  })

  it.each([
    { ...completedJob, job_id: 'another-job' },
    { ...completedJob, document_id: 'another-document' },
  ])('rejects a mismatched status lookup response', async (payload) => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse(payload))

    await expect(
      getAnalysisJob('job-test', 'document-test', 'test-token', fetcher),
    ).rejects.toMatchObject({ kind: 'invalid-response' })
  })
})
