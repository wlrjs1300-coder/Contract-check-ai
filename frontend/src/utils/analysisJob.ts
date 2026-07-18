import { ApiError } from '../api/http'
import type { AnalysisJobStatus } from '../types/analysisJobs'

export function getAnalysisRequestErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.kind === 'network') {
    return '서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.'
  }

  return '분석 요청을 완료하지 못했습니다. 분석 시작을 다시 눌러 주세요.'
}

export function getAnalysisRefreshErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.kind === 'network') {
    return '서버에 연결하지 못했습니다. 기존 작업 상태는 유지됩니다. 잠시 후 다시 시도해 주세요.'
  }

  return '분석 상태를 확인하지 못했습니다. 기존 작업 상태는 유지됩니다. 다시 시도해 주세요.'
}

export function getAnalysisStatusMessage(status: AnalysisJobStatus): string {
  switch (status) {
    case 'queued':
      return '분석 작업이 대기 중입니다.'
    case 'processing':
      return '분석 작업을 처리 중입니다.'
    case 'completed':
      return '분석 작업이 완료되었습니다.'
    case 'failed':
      return '분석 작업을 완료하지 못했습니다. 다시 시도해 주세요.'
  }
}
