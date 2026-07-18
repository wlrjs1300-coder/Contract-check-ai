import type {
  AnalysisDisplayLabel,
  AnalysisResultItem,
  AnalysisResults,
} from '../types/analysisResults'
import type { AnalysisJobStatus } from '../types/analysisJobs'
import { apiConfig } from './config'
import { ApiError, readErrorDetail, readJsonResponse } from './http'

type Fetcher = typeof fetch

const STATUSES: ReadonlySet<AnalysisJobStatus> = new Set([
  'queued',
  'processing',
  'completed',
  'failed',
])
const LABELS: ReadonlySet<AnalysisDisplayLabel> = new Set([
  '안전',
  '주의',
  '위험',
  '추가 확인',
])

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function isResultItem(value: unknown): value is AnalysisResultItem {
  if (typeof value !== 'object' || value === null) return false

  return (
    'clause_id' in value &&
    isNonEmptyString(value.clause_id) &&
    'reference_id' in value &&
    isNonEmptyString(value.reference_id) &&
    'display_label' in value &&
    typeof value.display_label === 'string' &&
    LABELS.has(value.display_label as AnalysisDisplayLabel) &&
    'summary' in value &&
    typeof value.summary === 'string' &&
    'expert_review_recommended' in value &&
    typeof value.expert_review_recommended === 'boolean'
  )
}

function isAnalysisResults(value: unknown): value is AnalysisResults {
  if (typeof value !== 'object' || value === null) return false
  if (
    !('document_id' in value) ||
    !isNonEmptyString(value.document_id) ||
    !('job_id' in value) ||
    !isNonEmptyString(value.job_id) ||
    !('status' in value) ||
    typeof value.status !== 'string' ||
    !STATUSES.has(value.status as AnalysisJobStatus) ||
    !('items' in value) ||
    !Array.isArray(value.items) ||
    !value.items.every(isResultItem)
  ) {
    return false
  }

  const clauseIds = new Set(value.items.map((item) => item.clause_id))
  const referenceIds = new Set(value.items.map((item) => item.reference_id))
  return clauseIds.size === value.items.length && referenceIds.size === value.items.length
}

export async function getAnalysisResults(
  documentId: string,
  jobId: string,
  fetcher: Fetcher = fetch,
): Promise<AnalysisResults> {
  if (!isNonEmptyString(documentId) || !isNonEmptyString(jobId)) {
    throw new ApiError('invalid-response', 'An analysis result identifier was empty.')
  }

  let response: Response
  try {
    response = await fetcher(
      `${apiConfig.baseUrl}/documents/${encodeURIComponent(documentId)}/analysis-results`,
      { method: 'GET' },
    )
  } catch {
    throw new ApiError('network', 'The analysis results request failed.')
  }

  const payload = await readJsonResponse(response)
  if (!response.ok) {
    throw new ApiError('http', 'The analysis results request was rejected.', {
      status: response.status,
      detail: readErrorDetail(payload) ?? undefined,
    })
  }

  if (
    !isAnalysisResults(payload) ||
    payload.document_id !== documentId ||
    payload.job_id !== jobId
  ) {
    throw new ApiError('invalid-response', 'The analysis results response was invalid.')
  }

  return payload
}
