export function normalizeBaseUrl(url: string): string {
  return url.trim().replace(/\/+$/, '')
}
