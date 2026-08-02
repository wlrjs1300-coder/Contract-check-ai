import { afterEach, describe, expect, it } from 'vitest'
import { ACCESS_TOKEN_KEY, clearAccessToken, readAccessToken, storeAccessToken } from './session'

afterEach(() => sessionStorage.clear())

describe('access token session', () => {
  it('stores only the access token under the scoped key', () => {
    storeAccessToken('test-token')
    expect(readAccessToken()).toBe('test-token')
    expect(sessionStorage.length).toBe(1)
    expect(sessionStorage.key(0)).toBe(ACCESS_TOKEN_KEY)
    expect(JSON.stringify(sessionStorage)).not.toContain('password')
    expect(JSON.stringify(sessionStorage)).not.toContain('user@example.invalid')
  })

  it('removes the token on logout', () => {
    storeAccessToken('test-token')
    clearAccessToken()
    expect(readAccessToken()).toBeNull()
  })

  it('rejects an empty token', () => {
    expect(() => storeAccessToken('  ')).toThrow()
    expect(sessionStorage.length).toBe(0)
  })
})
