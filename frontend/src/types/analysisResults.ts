import type { AnalysisJobStatus } from './analysisJobs'

export type AnalysisDisplayLabel = '안전' | '주의' | '위험' | '추가 확인'

export type AnalysisResultItem = Readonly<{
  clause_id: string
  reference_id: string
  display_label: AnalysisDisplayLabel
  summary: string
  expert_review_recommended: boolean
}>

export type AnalysisResults = Readonly<{
  document_id: string
  job_id: string
  status: AnalysisJobStatus
  items: AnalysisResultItem[]
}>
