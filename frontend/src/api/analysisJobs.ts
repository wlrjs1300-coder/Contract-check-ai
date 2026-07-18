import type { AnalysisJob, AnalysisJobStatus } from '../types/analysisJobs'
import { apiConfig } from './config'
import { ApiError, readErrorDetail, readJsonResponse } from './http'

type Fetcher = typeof fetch

const ANALYSIS_JOB_STATUSES: ReadonlySet<AnalysisJobStatus> = new Set([
  'queued',
  'processing',
  'completed',
  'failed',
])

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function requireIdentifier(value: string): void {
  if (!isNonEmptyString(value)) {
    throw new ApiError('invalid-response', 'An analysis job identifier was empty.')
  }
}

function isAnalysisJob(value: unknown): value is AnalysisJob {
  if (typeof value !== 'object' || value === null) {
    return false
  }

  return (
    'job_id' in value &&
    isNonEmptyString(value.job_id) &&
    'document_id' in value &&
    isNonEmptyString(value.document_id) &&
    'status' in value &&
    typeof value.status === 'string' &&
    ANALYSIS_JOB_STATUSES.has(value.status as AnalysisJobStatus)
  )
}

async function requestAnalysisJob(
  url: string,
  init: RequestInit,
  expected: Readonly<{ documentId: string; jobId?: string }>,
  fetcher: Fetcher,
): Promise<AnalysisJob> {
  let response: Response

  try {
    response = await fetcher(url, init)
  } catch {
    throw new ApiError('network', 'The analysis job request failed.')
  }

  const payload = await readJsonResponse(response)

  if (!response.ok) {
    throw new ApiError('http', 'The analysis job request was rejected.', {
      status: response.status,
      detail: readErrorDetail(payload) ?? undefined,
    })
  }

  if (
    !isAnalysisJob(payload) ||
    payload.document_id !== expected.documentId ||
    (expected.jobId !== undefined && payload.job_id !== expected.jobId)
  ) {
    throw new ApiError('invalid-response', 'The analysis job response was invalid.')
  }

  return payload
}

export async function createAnalysisJob(
  documentId: string,
  fetcher: Fetcher = fetch,
): Promise<AnalysisJob> {
  requireIdentifier(documentId)
  const encodedDocumentId = encodeURIComponent(documentId)

  return requestAnalysisJob(
    `${apiConfig.baseUrl}/documents/${encodedDocumentId}/analysis-jobs`,
    { method: 'POST' },
    { documentId },
    fetcher,
  )
}

export async function getAnalysisJob(
  jobId: string,
  documentId: string,
  fetcher: Fetcher = fetch,
): Promise<AnalysisJob> {
  requireIdentifier(jobId)
  requireIdentifier(documentId)
  const encodedJobId = encodeURIComponent(jobId)

  return requestAnalysisJob(
    `${apiConfig.baseUrl}/analysis-jobs/${encodedJobId}`,
    { method: 'GET' },
    { documentId, jobId },
    fetcher,
  )
}
