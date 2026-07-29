import type { ReactNode } from 'react'
import { TopNavigation, type AppPage } from './TopNavigation'

type AppFrameProps = Readonly<{
  currentPage: AppPage
  children: ReactNode
  onNavigate: (page: AppPage) => void
}>

export function AppFrame({ currentPage, children, onNavigate }: AppFrameProps) {
  return (
    <div className="app-shell">
      <TopNavigation currentPage={currentPage} onNavigate={onNavigate} />
      <div className="app-workspace">
        <main className="app-content">
          <div className="page-transition" key={currentPage}>{children}</div>
        </main>
        <footer className="site-footer">
          <div className="footer-main">
            <div className="footer-brand">
              <strong>PACTA</strong>
              <span>계약 문서 검토 지원 서비스</span>
            </div>
            <nav aria-label="푸터 메뉴">
              <strong>서비스</strong>
              <button type="button" onClick={() => onNavigate('home')}>홈</button>
              <button type="button" onClick={() => onNavigate('analyze')}>계약서 분석</button>
              <button type="button" onClick={() => onNavigate('results')}>분석 결과</button>
            </nav>
            <div className="footer-scope">
              <strong>지원 범위</strong>
              <span>UTF-8 TXT</span>
              <span>최대 1MB · 한 번에 한 파일</span>
            </div>
          </div>
          <div className="footer-bottom">
            <span>© 2026 PACTA</span>
            <span>분석 결과는 법률 자문이나 최종 판단을 대신하지 않습니다.</span>
          </div>
        </footer>
      </div>
    </div>
  )
}
