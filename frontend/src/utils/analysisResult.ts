import { ApiError } from '../api/http'
import type { AnalysisResultItem } from '../types/analysisResults'
import type { DocumentClause } from '../types/documents'

export type LinkedAnalysisResult = Readonly<{
  clause: DocumentClause
  result: AnalysisResultItem
}>

export function linkAnalysisResults(
  clauses: DocumentClause[],
  items: AnalysisResultItem[],
): LinkedAnalysisResult[] {
  if (clauses.length !== items.length) {
    throw new ApiError('invalid-response', 'Analysis result clause coverage was invalid.')
  }

  const byClauseId = new Map(items.map((item) => [item.clause_id, item]))
  const linked = [...clauses]
    .sort((left, right) => left.ordinal - right.ordinal)
    .map((clause) => {
      const result = byClauseId.get(clause.clause_id)
      if (result === undefined || result.reference_id !== clause.reference_id) {
        throw new ApiError('invalid-response', 'Analysis result clause linkage was invalid.')
      }
      return { clause, result }
    })

  if (new Set(clauses.map((clause) => clause.clause_id)).size !== clauses.length) {
    throw new ApiError('invalid-response', 'Document clause identifiers were invalid.')
  }
  return linked
}

export function getAnalysisResultsErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.kind === 'network') {
      return '서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.'
    }
    if (
      error.kind === 'http' &&
      error.status === 404 &&
      error.detail === 'Analysis result not found.'
    ) {
      return '저장된 분석 결과를 찾지 못했습니다.'
    }
  }
  return '분석 결과를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.'
}

export const ANALYSIS_LINK_ERROR_MESSAGE =
  '분석 결과와 문서 조항을 연결하지 못했습니다. 다시 분석해 주세요.'
