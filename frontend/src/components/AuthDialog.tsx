import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ApiError } from '../api/http'

export type AuthMode = 'login' | 'register'

type AuthDialogProps = Readonly<{
  mode: AuthMode | null
  notice: string | null
  onClose: () => void
  onLogin: (email: string, password: string) => Promise<void>
  onRegister: (email: string, password: string) => Promise<void>
  onModeChange: (mode: AuthMode) => void
}>

const EMAIL_MESSAGE = '올바른 이메일 형식을 입력해 주세요.'
const PASSWORD_MESSAGE = '비밀번호는 12자 이상 128자 이하로 입력해 주세요.'

function normalizeEmail(value: string): string {
  return value.trim().toLowerCase()
}

function validEmail(value: string): boolean {
  const parts = value.split('@')
  return value.length <= 254 && parts.length === 2 && parts[0].length > 0 && parts[1].includes('.')
}

function authErrorMessage(error: unknown, mode: AuthMode): string {
  if (error instanceof ApiError) {
    if (error.status === 429) return '요청이 많습니다. 잠시 후 다시 시도해 주세요.'
    if (error.kind === 'network') return '서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.'
    if (error.kind === 'invalid-response') return '서버 응답을 확인할 수 없습니다. 잠시 후 다시 시도해 주세요.'
    if (mode === 'register' && error.status === 409) return '이미 가입된 이메일입니다.'
    if (mode === 'login' && error.status === 401) return '이메일 또는 비밀번호를 확인해 주세요.'
  }
  return mode === 'login'
    ? '로그인하지 못했습니다. 잠시 후 다시 시도해 주세요.'
    : '회원가입하지 못했습니다. 잠시 후 다시 시도해 주세요.'
}

export function AuthDialog(props: AuthDialogProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const emailRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (props.mode === null) return
    emailRef.current?.focus()
  }, [props.mode])

  useEffect(() => {
    if (props.mode === null) return
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape' && !submitting) props.onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [props, submitting])

  if (props.mode === null) return null
  const mode = props.mode

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting) return
    const normalizedEmail = normalizeEmail(email)
    if (!validEmail(normalizedEmail)) {
      setError(EMAIL_MESSAGE)
      return
    }
    if (password.length < 12 || password.length > 128) {
      setError(PASSWORD_MESSAGE)
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      if (mode === 'login') await props.onLogin(normalizedEmail, password)
      else await props.onRegister(normalizedEmail, password)
    } catch (requestError) {
      setError(authErrorMessage(requestError, mode))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget && !submitting) props.onClose()
    }}>
      <section className="auth-dialog" role="dialog" aria-modal="true" aria-labelledby="auth-title">
        <button className="auth-close" type="button" aria-label="닫기" disabled={submitting} onClick={props.onClose}>×</button>
        <p className="section-label">Account</p>
        <h2 id="auth-title">{mode === 'login' ? '로그인' : '회원가입'}</h2>
        {props.notice && <p className="alert alert-info" role="status">{props.notice}</p>}
        {error && <p className="alert alert-danger" role="alert">{error}</p>}
        <form onSubmit={handleSubmit} noValidate>
          <label htmlFor="auth-email">이메일</label>
          <input ref={emailRef} id="auth-email" type="email" value={email} autoComplete={mode === 'login' ? 'username' : 'email'} disabled={submitting} onChange={(event) => setEmail(event.target.value)} />
          <label htmlFor="auth-password">비밀번호</label>
          <input id="auth-password" type="password" value={password} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} disabled={submitting} onChange={(event) => setPassword(event.target.value)} />
          <button className="btn btn-primary" type="submit" disabled={submitting}>{submitting ? '처리 중…' : mode === 'login' ? '로그인' : '회원가입'}</button>
        </form>
        <button className="auth-mode-switch" type="button" disabled={submitting} onClick={() => props.onModeChange(mode === 'login' ? 'register' : 'login')}>
          {mode === 'login' ? '회원가입으로 이동' : '로그인으로 이동'}
        </button>
      </section>
    </div>
  )
}
