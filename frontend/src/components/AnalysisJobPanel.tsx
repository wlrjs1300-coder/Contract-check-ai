import type { AnalysisJob } from '../types/analysisJobs'
import { getAnalysisStatusMessage } from '../utils/analysisJob'

type AnalysisJobPanelProps = Readonly<{
  canStart: boolean
  isCreating: boolean
  isRefreshing: boolean
  isLoadingResults: boolean
  job: AnalysisJob | null
  requestError: string | null
  refreshError: string | null
  onStart: () => void
  onRefresh: () => void
  onViewResults: () => void
}>

export function AnalysisJobPanel({
  canStart,
  isCreating,
  isRefreshing,
  isLoadingResults,
  job,
  requestError,
  refreshError,
  onStart,
  onRefresh,
  onViewResults,
}: AnalysisJobPanelProps) {
  const canRefresh =
    job !== null && (job.status === 'queued' || job.status === 'processing')
  const isBusy = isCreating || isRefreshing || isLoadingResults
  const canCreateJob = canStart && !canRefresh

  return (
    <section
      className="card border-0 shadow-sm"
      aria-labelledby="analysis-title"
      aria-busy={isBusy}
    >
      <div className="card-body p-4">
        <h2 id="analysis-title" className="h4">
          분석 작업 상태
        </h2>
        <p className="text-secondary">
          현재 분석 작업과 결과는 화면과 API 흐름 검증을 위한 합성 처리입니다.
          실제 외부 분석 품질이나 법률 판단을 의미하지 않습니다.
        </p>

        {!canStart && job === null && (
          <p className="alert alert-secondary">
            분리된 조항이 없어 분석을 시작할 수 없습니다. 문서 형식과 조항
            표기를 확인해 주세요.
          </p>
        )}

        <div aria-live="polite">
          {isCreating && <p className="alert alert-info">분석을 요청하고 있습니다.</p>}
          {isRefreshing && <p className="alert alert-info">분석 상태를 확인하고 있습니다.</p>}
          {!isBusy && job && (
            <p className={`alert ${job.status === 'failed' ? 'alert-danger' : 'alert-info'}`}>
              {getAnalysisStatusMessage(job.status)}
            </p>
          )}
        </div>

        {requestError && (
          <p className="alert alert-danger" role="alert">
            {requestError}
          </p>
        )}
        {refreshError && (
          <p className="alert alert-warning" role="alert">
            {refreshError}
          </p>
        )}

        <div className="d-flex flex-wrap gap-2">
          <button
            type="button"
            className="btn btn-primary"
            disabled={!canCreateJob || isBusy}
            onClick={onStart}
          >
            {isCreating ? '분석 요청 중…' : '분석 시작'}
          </button>
          {canRefresh && (
            <button
              type="button"
              className="btn btn-outline-primary"
              disabled={isBusy}
              onClick={onRefresh}
            >
              {isRefreshing ? '상태 확인 중…' : '상태 다시 확인'}
            </button>
          )}
          {job?.status === 'completed' && (
            <button
              type="button"
              className="btn btn-outline-primary"
              disabled={isBusy}
              onClick={onViewResults}
            >
              {isLoadingResults ? '결과 불러오는 중…' : '분석 결과 보기'}
            </button>
          )}
        </div>
      </div>
    </section>
  )
}
