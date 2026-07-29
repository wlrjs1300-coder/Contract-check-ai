import type { ReactNode } from 'react'
import type { AppPage } from '../components/TopNavigation'

const BENEFITS: ReadonlyArray<Readonly<{
  title: string
  icon: ReactNode
}>> = [
  {
    title: '조항별 핵심 확인',
    icon: <><path d="M6 3.5h9l3 3v14H6z" /><path d="M15 3.5v3h3M9 11h6M9 15h4" /></>,
  },
  {
    title: '원문·결과 비교',
    icon: <><rect x="3.5" y="5" width="7" height="14" rx="1" /><rect x="13.5" y="5" width="7" height="14" rx="1" /><path d="M6 9h2M6 12h2M16 9h2M16 12h2" /></>,
  },
  {
    title: '검토 필요 항목 안내',
    icon: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5v5M12 16.5h.01" /></>,
  },
]

const PROCESS: ReadonlyArray<Readonly<{
  number: string
  title: string
  icon: ReactNode
}>> = [
  {
    number: '01',
    title: '계약서 등록',
    icon: <><path d="M7 3.5h7l3 3v14H7z" /><path d="M14 3.5v3h3M12 16V10M9.5 12.5 12 10l2.5 2.5" /></>,
  },
  {
    number: '02',
    title: '보호 후 분석',
    icon: <><path d="M12 3.5 18 6v5c0 4.2-2.5 7.3-6 9-3.5-1.7-6-4.8-6-9V6z" /><path d="m9.5 12 1.7 1.7 3.5-3.8" /></>,
  },
  {
    number: '03',
    title: '결과 확인',
    icon: <><path d="M5 4.5h14v15H5z" /><path d="M8.5 9h7M8.5 13h4M15 15.5l1.2 1.2 2.3-2.6" /></>,
  },
]

type HomePageProps = Readonly<{ onNavigate: (page: AppPage) => void }>

export function HomePage({ onNavigate }: HomePageProps) {
  return (
    <div className="page home-page">
      <section className="client-hero" aria-labelledby="home-title">
        <div className="client-hero-copy">
          <p className="section-label">Contract review assistant</p>
          <h1 id="home-title">
            복잡한 계약서,
            <span>핵심만 빠르게 확인하세요.</span>
          </h1>
          <p className="hero-description">
            <strong>계약서 한 번 업로드로</strong>
            <span>조항별 핵심과 검토 필요 항목까지 확인하세요.</span>
          </p>
          <div className="hero-actions">
            <button type="button" className="btn btn-primary" onClick={() => onNavigate('analyze')}>
              계약서 분석 시작
            </button>
            <ul className="upload-spec" aria-label="업로드 조건">
              <li>TXT</li><li>최대 1MB</li><li>한 번에 한 파일</li>
            </ul>
          </div>
        </div>

        <div className="process-visual" aria-label="문서 검토 처리 과정">
          <div className="process-visual-heading"><strong>3단계로 간단하게</strong></div>
          <ol>
            {PROCESS.map(({ number, title, icon }, index) => (
              <li key={number}>
                <span className="process-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{icon}</svg>
                </span>
                <div className="process-copy"><small>{number}</small><strong>{title}</strong></div>
                {index < PROCESS.length - 1 && <span className="process-arrow" aria-hidden="true">↓</span>}
              </li>
            ))}
          </ol>
          <div className="process-proof">
            <span aria-hidden="true">✓</span>
            <div><strong>원문 연결 검증</strong><small>결과와 해당 조항을 함께 표시합니다</small></div>
          </div>
        </div>
      </section>

      <section className="benefit-section" aria-labelledby="benefit-title">
        <div className="benefit-heading">
          <span>한 번의 분석으로</span>
          <h2 id="benefit-title">필요한 내용만 한눈에</h2>
        </div>
        <div className="benefit-grid">
          {BENEFITS.map(({ title, icon }) => (
            <article key={title}>
              <span className="benefit-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">{icon}</svg>
              </span>
              <h3>{title}</h3>
            </article>
          ))}
        </div>
      </section>

    </div>
  )
}
