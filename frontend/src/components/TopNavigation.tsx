import pactaLogo from '../assets/PACTA_logo.png'
import type { AuthStatus, AuthUser } from '../types/auth'
import type { AuthMode } from './AuthDialog'

export type AppPage = 'home' | 'analyze' | 'results'

const PAGE_LINKS: ReadonlyArray<Readonly<{
  page: AppPage
  label: string
  href: string
}>> = [
  { page: 'home', label: '홈', href: '/' },
  { page: 'analyze', label: '계약서 분석', href: '/analyze' },
  { page: 'results', label: '분석 결과', href: '/results' },
]

type TopNavigationProps = Readonly<{
  currentPage: AppPage
  onNavigate: (page: AppPage) => void
  authStatus: AuthStatus
  currentUser: AuthUser | null
  onOpenAuth: (mode: AuthMode) => void
  onLogout: () => void
}>

export function TopNavigation({ currentPage, onNavigate, authStatus, currentUser, onOpenAuth, onLogout }: TopNavigationProps) {
  return (
    <header className="app-navbar">
      <a
        className="brand-link"
        href="/"
        aria-label="PACTA 홈"
        onClick={(event) => {
          event.preventDefault()
          onNavigate('home')
        }}
      >
        <span className="brand-wordmark" aria-hidden="true">
          <img src={pactaLogo} alt="" />
        </span>
      </a>

      <nav className="top-navigation" aria-label="페이지 메뉴">
        {PAGE_LINKS.map(({ page, label, href }) => (
          <a
            href={href}
            aria-label={label}
            aria-current={currentPage === page ? 'page' : undefined}
            key={page}
            onClick={(event) => {
              event.preventDefault()
              onNavigate(page)
            }}
          >
            <strong>{label}</strong>
          </a>
        ))}
      </nav>
      <div className="auth-navigation" aria-label="인증 메뉴">
        {authStatus === 'checking' && <span role="status">인증 확인 중…</span>}
        {authStatus === 'anonymous' && (
          <>
            <button type="button" onClick={() => onOpenAuth('login')}>로그인</button>
            <span aria-hidden="true">|</span>
            <button type="button" onClick={() => onOpenAuth('register')}>회원가입</button>
          </>
        )}
        {authStatus === 'authenticated' && currentUser && (
          <>
            <span className="auth-email" title={currentUser.email}>{currentUser.email}</span>
            <button type="button" onClick={onLogout}>로그아웃</button>
          </>
        )}
      </div>
    </header>
  )
}
