import { describe, expect, it } from 'vitest'
import { getApiBaseUrl } from './config'

describe('getApiBaseUrl', () => {
  it('returns the local API URL by default', () => {
    expect(getApiBaseUrl('')).toBe('http://localhost:8000')
    expect(getApiBaseUrl('   ')).toBe('http://localhost:8000')
  })

  it('trims spaces and removes trailing slashes', () => {
    expect(getApiBaseUrl('  https://api.example.test///  ')).toBe(
      'https://api.example.test',
    )
  })

  it('keeps the URL protocol intact', () => {
    expect(getApiBaseUrl('http://localhost:8000/')).toBe(
      'http://localhost:8000',
    )
  })
})
