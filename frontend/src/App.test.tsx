import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('App', () => {
  it('renders the service name', () => {
    render(<App />)

    expect(screen.getByText('ContractCheck AI')).toBeInTheDocument()
  })

  it('renders the scaffold completion message', () => {
    render(<App />)

    expect(
      screen.getByText('프론트엔드 기반 구성이 완료되었습니다.'),
    ).toBeInTheDocument()
  })
})
