export const ACCESS_TOKEN_KEY = 'contract-check.access-token'

export function readAccessToken(): string | null {
  const token = sessionStorage.getItem(ACCESS_TOKEN_KEY)
  return token && token.trim().length > 0 ? token : null
}

export function storeAccessToken(token: string): void {
  if (token.trim().length === 0) throw new Error('Access token must not be empty.')
  sessionStorage.setItem(ACCESS_TOKEN_KEY, token)
}

export function clearAccessToken(): void {
  sessionStorage.removeItem(ACCESS_TOKEN_KEY)
}
