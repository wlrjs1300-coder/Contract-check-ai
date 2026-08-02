import { describe, expect, it, vi } from 'vitest'
import { getCurrentUser, login, register } from './auth'

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } })
}

const user = {
  user_id: 'user-test',
  email: 'user@example.invalid',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
}

describe('auth API', () => {
  it('registers with the exact URL, method, and JSON body', async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse(user))
    await expect(register('user@example.invalid', 'synthetic-passphrase', fetcher)).resolves.toEqual(user)
    expect(fetcher).toHaveBeenCalledWith('http://localhost:8000/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'user@example.invalid', password: 'synthetic-passphrase' }),
    })
  })

  it('logs in and validates the response', async () => {
    const payload = { access_token: 'test-token', token_type: 'bearer', expires_in: 900 }
    const fetcher = vi.fn().mockResolvedValue(jsonResponse(payload))
    await expect(login('user@example.invalid', 'synthetic-passphrase', fetcher)).resolves.toEqual(payload)
    expect(fetcher).toHaveBeenCalledWith('http://localhost:8000/auth/login', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ email: 'user@example.invalid', password: 'synthetic-passphrase' }),
    }))
  })

  it('rejects an invalid login response', async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse({ access_token: '', token_type: 'bearer', expires_in: 900 }))
    await expect(login('user@example.invalid', 'synthetic-passphrase', fetcher)).rejects.toMatchObject({ kind: 'invalid-response' })
  })

  it('sends bearer authorization to auth me', async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse(user))
    await expect(getCurrentUser('test-token', fetcher)).resolves.toEqual(user)
    const [, init] = fetcher.mock.calls[0]
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer test-token')
  })

  it('rejects an empty token before requesting auth me', async () => {
    const fetcher = vi.fn()
    await expect(getCurrentUser('  ', fetcher)).rejects.toMatchObject({ kind: 'invalid-response' })
    expect(fetcher).not.toHaveBeenCalled()
  })

  it('classifies JSON HTTP, non-JSON, and network failures', async () => {
    const httpFetcher = vi.fn().mockResolvedValue(jsonResponse({ detail: 'safe-detail' }, 401))
    await expect(login('user@example.invalid', 'synthetic-passphrase', httpFetcher)).rejects.toMatchObject({ kind: 'http', status: 401, detail: 'safe-detail' })
    const nonJsonFetcher = vi.fn().mockResolvedValue(new Response('no', { status: 500 }))
    await expect(login('user@example.invalid', 'synthetic-passphrase', nonJsonFetcher)).rejects.toMatchObject({ kind: 'http', status: 500 })
    const networkFetcher = vi.fn().mockRejectedValue(new TypeError('offline'))
    await expect(login('user@example.invalid', 'synthetic-passphrase', networkFetcher)).rejects.toMatchObject({ kind: 'network' })
  })
})
