export type AnalysisJobStatus =
  | 'queued'
  | 'processing'
  | 'completed'
  | 'failed'

export type AnalysisJob = Readonly<{
  job_id: string
  document_id: string
  status: AnalysisJobStatus
}>
