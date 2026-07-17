import { StatusPanel } from '../components/StatusPanel'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import brandMark from '../assets/brand-mark.svg'

export function ScaffoldPage() {
  useDocumentTitle('ContractCheck AI')

  return (
    <main className="container py-5">
      <header className="mb-4">
        <div className="d-flex align-items-center gap-3 mb-3">
          <img src={brandMark} width="48" height="48" alt="" />
          <p className="text-uppercase text-primary fw-semibold mb-0">
            ContractCheck AI
          </p>
        </div>
        <h1 className="display-6 fw-bold">프론트엔드 기반 구성이 완료되었습니다.</h1>
        <p className="lead text-secondary mb-0">
          현재는 실제 계약서 분석 기능이 아닌 로컬 통합 준비 단계입니다.
        </p>
      </header>

      <StatusPanel
        title="백엔드 연결 상태"
        description="다음 단계에서 로컬 API 연결 상태를 확인합니다."
      />
    </main>
  )
}
