import type { UploadedDocument } from '../types/documents'
import { apiConfig } from './config'
import { ApiError, readErrorDetail, readJsonResponse } from './http'

type Fetcher = typeof fetch

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}

function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0
}

function isPositiveInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value > 0
}

function isDocumentClause(value: unknown): boolean {
  if (typeof value !== 'object' || value === null) {
    return false
  }

  return (
    'clause_id' in value &&
    typeof value.clause_id === 'string' &&
    'reference_id' in value &&
    typeof value.reference_id === 'string' &&
    'source_hash' in value &&
    typeof value.source_hash === 'string' &&
    'ordinal' in value &&
    isPositiveInteger(value.ordinal) &&
    'marker' in value &&
    typeof value.marker === 'string' &&
    'clause_type' in value &&
    typeof value.clause_type === 'string' &&
    'title' in value &&
    (typeof value.title === 'string' || value.title === null) &&
    'body' in value &&
    typeof value.body === 'string' &&
    'warnings' in value &&
    isStringArray(value.warnings)
  )
}

function isUploadedDocument(value: unknown): value is UploadedDocument {
  if (typeof value !== 'object' || value === null) {
    return false
  }

  return (
    'document_id' in value &&
    typeof value.document_id === 'string' &&
    'filename' in value &&
    typeof value.filename === 'string' &&
    'content_type' in value &&
    (typeof value.content_type === 'string' || value.content_type === null) &&
    'size_bytes' in value &&
    isNonNegativeInteger(value.size_bytes) &&
    'character_count' in value &&
    isNonNegativeInteger(value.character_count) &&
    'status' in value &&
    typeof value.status === 'string' &&
    'clause_count' in value &&
    isNonNegativeInteger(value.clause_count) &&
    'clauses' in value &&
    Array.isArray(value.clauses) &&
    value.clauses.every(isDocumentClause) &&
    value.clause_count === value.clauses.length &&
    'unclassified_sections' in value &&
    isStringArray(value.unclassified_sections) &&
    'document_warnings' in value &&
    isStringArray(value.document_warnings)
  )
}

export async function uploadDocument(
  file: File,
  fetcher: Fetcher = fetch,
): Promise<UploadedDocument> {
  const formData = new FormData()
  formData.append('file', file)

  let response: Response

  try {
    response = await fetcher(`${apiConfig.baseUrl}/documents/upload`, {
      method: 'POST',
      body: formData,
    })
  } catch {
    throw new ApiError('network', 'The document upload request failed.')
  }

  const payload = await readJsonResponse(response)

  if (!response.ok) {
    throw new ApiError('http', 'The document upload was rejected.', {
      status: response.status,
      detail: readErrorDetail(payload) ?? undefined,
    })
  }

  if (!isUploadedDocument(payload)) {
    throw new ApiError(
      'invalid-response',
      'The document upload response was invalid.',
    )
  }

  return payload
}
