import type { ApiConfig } from '../types/config'
import { normalizeBaseUrl } from '../utils/normalizeBaseUrl'

const DEFAULT_API_BASE_URL = 'http://localhost:8000'

export function getApiBaseUrl(
  configuredUrl: string | undefined = import.meta.env.VITE_API_BASE_URL,
): string {
  const normalizedUrl = normalizeBaseUrl(configuredUrl ?? '')

  return normalizedUrl || DEFAULT_API_BASE_URL
}

export const apiConfig: ApiConfig = {
  baseUrl: getApiBaseUrl(),
}
