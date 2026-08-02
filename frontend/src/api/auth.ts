import type { AuthUser, LoginResponse } from '../types/auth'
import { apiConfig } from './config'
import { authenticatedRequest, type Fetcher } from './authenticatedRequest'
import { ApiError, readErrorDetail, readJsonResponse } from './http'

function isAuthUser(value: unknown): value is AuthUser {
  return typeof value === 'object' && value !== null &&
    'user_id' in value && typeof value.user_id === 'string' && value.user_id.trim().length > 0 &&
    'email' in value && typeof value.email === 'string' && value.email.trim().length > 0 &&
    'is_active' in value && typeof value.is_active === 'boolean' &&
    'created_at' in value && typeof value.created_at === 'string'
}

function isLoginResponse(value: unknown): value is LoginResponse {
  return typeof value === 'object' && value !== null &&
    'access_token' in value && typeof value.access_token === 'string' && value.access_token.trim().length > 0 &&
    'token_type' in value && value.token_type === 'bearer' &&
    'expires_in' in value && typeof value.expires_in === 'number' && Number.isInteger(value.expires_in) && value.expires_in > 0
}

async function jsonRequest(
  url: string,
  init: RequestInit,
  fetcher: Fetcher,
): Promise<unknown> {
  let response: Response
  try {
    response = await fetcher(url, init)
  } catch {
    throw new ApiError('network', 'The authentication request failed.')
  }
  const payload = await readJsonResponse(response)
  if (!response.ok) {
    throw new ApiError('http', 'The authentication request was rejected.', {
      status: response.status,
      detail: readErrorDetail(payload) ?? undefined,
    })
  }
  return payload
}

export async function register(
  email: string,
  password: string,
  fetcher: Fetcher = fetch,
): Promise<AuthUser> {
  const payload = await jsonRequest(`${apiConfig.baseUrl}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  }, fetcher)
  if (!isAuthUser(payload)) throw new ApiError('invalid-response', 'The registration response was invalid.')
  return payload
}

export async function login(
  email: string,
  password: string,
  fetcher: Fetcher = fetch,
): Promise<LoginResponse> {
  const payload = await jsonRequest(`${apiConfig.baseUrl}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  }, fetcher)
  if (!isLoginResponse(payload)) throw new ApiError('invalid-response', 'The login response was invalid.')
  return payload
}

export async function getCurrentUser(
  accessToken: string,
  fetcher: Fetcher = fetch,
): Promise<AuthUser> {
  let response: Response
  try {
    response = await authenticatedRequest(fetcher, `${apiConfig.baseUrl}/auth/me`, accessToken, { method: 'GET' })
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError('network', 'The session verification request failed.')
  }
  const payload = await readJsonResponse(response)
  if (!response.ok) {
    throw new ApiError('http', 'The session verification request was rejected.', {
      status: response.status,
      detail: readErrorDetail(payload) ?? undefined,
    })
  }
  if (!isAuthUser(payload)) throw new ApiError('invalid-response', 'The session verification response was invalid.')
  return payload
}
