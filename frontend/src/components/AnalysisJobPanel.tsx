import type { AnalysisJob } from '../types/analysisJobs'
import { getAnalysisStatusMessage } from '../utils/analysisJob'

type AnalysisJobPanelProps = Readonly<{
  canStart: boolean
  isCreating: boolean
  isRefreshing: boolean
  job: AnalysisJob | null
  requestError: string | null
  refreshError: string | null
  onStart: () => void
  onRefresh: () => void
}>

export function AnalysisJobPanel({
  canStart,
  isCreating,
  isRefreshing,
  job,
  requestError,
  refreshError,
  onStart,
  onRefresh,
}: AnalysisJobPanelProps) {
  const canRefresh =
    job !== null && (job.status === 'queued' || job.status === 'processing')
  const isBusy = isCreating || isRefreshing
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
          현재 분석 작업은 화면과 API 흐름 검증을 위한 합성 처리입니다. 상세
          결과 표시는 다음 단계에서 연결합니다.
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
        </div>
      </div>
    </section>
  )
}
