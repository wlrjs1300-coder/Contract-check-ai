import { describe, expect, it, vi } from 'vitest'
import type { UploadedDocument } from '../types/documents'
import { uploadDocument } from './documents'
import { ApiError } from './http'

const responsePayload: UploadedDocument = {
  document_id: 'document-test',
  filename: 'sample.txt',
  content_type: 'text/plain',
  size_bytes: 12,
  character_count: 6,
  status: 'processed',
  clause_count: 0,
  clauses: [],
  unclassified_sections: ['합성 문장'],
  document_warnings: [],
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), { status })
}

describe('uploadDocument', () => {
  it('posts the file as FormData without a manual Content-Type header', async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse(responsePayload))
    const file = new File(['합성 본문'], 'sample.txt', { type: 'text/plain' })

    await expect(uploadDocument(file, fetcher)).resolves.toEqual(responsePayload)

    expect(fetcher).toHaveBeenCalledOnce()
    const [url, options] = fetcher.mock.calls[0]
    expect(url).toBe('http://localhost:8000/documents/upload')
    expect(options.method).toBe('POST')
    expect(options.headers).toBeUndefined()
    expect(options.body).toBeInstanceOf(FormData)
    expect(options.body.get('file')).toBe(file)
  })

  it('preserves JSON error detail and HTTP status', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      jsonResponse({ detail: 'Only .txt files are allowed.' }, 400),
    )

    await expect(
      uploadDocument(new File(['x'], 'sample.txt'), fetcher),
    ).rejects.toMatchObject({
      kind: 'http',
      status: 400,
      detail: 'Only .txt files are allowed.',
    })
  })

  it('distinguishes a non-JSON HTTP error', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response('failure', { status: 500 }))

    await expect(
      uploadDocument(new File(['x'], 'sample.txt'), fetcher),
    ).rejects.toMatchObject({ kind: 'http', status: 500, detail: null })
  })

  it('distinguishes a network failure', async () => {
    const fetcher = vi.fn().mockRejectedValue(new TypeError('network unavailable'))

    await expect(
      uploadDocument(new File(['x'], 'sample.txt'), fetcher),
    ).rejects.toMatchObject({ kind: 'network', status: null })
  })

  it('rejects an unexpected successful response', async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse({ document_id: 'incomplete' }))

    await expect(
      uploadDocument(new File(['x'], 'sample.txt'), fetcher),
    ).rejects.toMatchObject({ kind: 'invalid-response' })
  })

  it('rejects invalid numeric fields and a mismatched clause count', async () => {
    const invalidPayloads = [
      { ...responsePayload, size_bytes: -1 },
      { ...responsePayload, character_count: 1.5 },
      { ...responsePayload, clause_count: -1 },
      {
        ...responsePayload,
        clause_count: 1,
      },
      {
        ...responsePayload,
        clause_count: 1,
        clauses: [
          {
            clause_id: 'clause-001',
            reference_id: 'document-test:clause:1',
            source_hash: 'hash',
            ordinal: 0,
            marker: '제1조',
            clause_type: 'normal',
            title: null,
            body: '합성 본문',
            warnings: [],
          },
        ],
      },
    ]

    for (const payload of invalidPayloads) {
      const fetcher = vi.fn().mockResolvedValue(jsonResponse(payload))

      await expect(
        uploadDocument(new File(['x'], 'sample.txt'), fetcher),
      ).rejects.toBeInstanceOf(ApiError)
    }
  })
})
