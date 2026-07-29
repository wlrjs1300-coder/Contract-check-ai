export type ApiErrorKind = 'http' | 'network' | 'invalid-response'

export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly status: number | null
  readonly detail: string | null

  constructor(
    kind: ApiErrorKind,
    message: string,
    options: Readonly<{ status?: number; detail?: string }> = {},
  ) {
    super(message)
    this.name = 'ApiError'
    this.kind = kind
    this.status = options.status ?? null
    this.detail = options.detail ?? null
  }
}

export async function readJsonResponse(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch {
    if (!response.ok) {
      throw new ApiError('http', 'The server returned a non-JSON error.', {
        status: response.status,
      })
    }

    throw new ApiError('invalid-response', 'The server response was not JSON.')
  }
}

export function readErrorDetail(payload: unknown): string | null {
  if (
    typeof payload === 'object' &&
    payload !== null &&
    'detail' in payload &&
    typeof payload.detail === 'string'
  ) {
    return payload.detail
  }

  return null
}
