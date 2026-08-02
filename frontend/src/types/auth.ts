export type AuthStatus = 'checking' | 'anonymous' | 'authenticated'

export type AuthUser = Readonly<{
  user_id: string
  email: string
  is_active: boolean
  created_at: string
}>

export type LoginResponse = Readonly<{
  access_token: string
  token_type: 'bearer'
  expires_in: number
}>
