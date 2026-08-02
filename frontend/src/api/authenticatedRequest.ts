import { ApiError } from './http'

export type Fetcher = typeof fetch

export function withBearerToken(
  accessToken: string,
  init: RequestInit = {},
): RequestInit {
  if (accessToken.trim().length === 0) {
    throw new ApiError('invalid-response', 'An access token was required.')
  }

  const headers = new Headers(init.headers)
  headers.set('Authorization', `Bearer ${accessToken}`)
  return { ...init, headers }
}

export function authenticatedRequest(
  fetcher: Fetcher,
  url: string,
  accessToken: string,
  init: RequestInit = {},
): Promise<Response> {
  return fetcher(url, withBearerToken(accessToken, init))
}
