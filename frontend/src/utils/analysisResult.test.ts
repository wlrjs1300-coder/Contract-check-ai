import { describe, expect, it } from 'vitest'
import type { AnalysisResultItem } from '../types/analysisResults'
import type { DocumentClause } from '../types/documents'
import { linkAnalysisResults } from './analysisResult'

const clauses: DocumentClause[] = [
  { clause_id: 'clause-2', reference_id: 'doc:clause:2', source_hash: 'hash-2', ordinal: 2, marker: '제2조', clause_type: 'normal', title: '두 번째', body: '합성 본문', warnings: [] },
  { clause_id: 'clause-1', reference_id: 'doc:clause:1', source_hash: 'hash-1', ordinal: 1, marker: '제1조', clause_type: 'normal', title: '첫 번째', body: '합성 본문', warnings: [] },
]
const items: AnalysisResultItem[] = [
  { clause_id: 'clause-2', reference_id: 'doc:clause:2', display_label: '주의', summary: '두 번째 결과', expert_review_recommended: true },
  { clause_id: 'clause-1', reference_id: 'doc:clause:1', display_label: '안전', summary: '첫 번째 결과', expert_review_recommended: false },
]

describe('analysis result linkage', () => {
  it('links both identifiers and orders results by clause ordinal', () => {
    expect(linkAnalysisResults(clauses, items).map(({ clause }) => clause.ordinal)).toEqual([1, 2])
  })

  it.each([
    ['unknown clause', [{ ...items[0], clause_id: 'other' }, items[1]]],
    ['reference mismatch', [{ ...items[0], reference_id: 'other' }, items[1]]],
    ['missing result', [items[0]]],
  ])('rejects %s', (_reason, invalidItems) => {
    expect(() => linkAnalysisResults(clauses, invalidItems)).toThrow()
  })
})
