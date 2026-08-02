import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

describe('responsive base styles', () => {
  it('does not force the body wider than a 320px viewport', () => {
    const stylesheet = readFileSync(
      resolve(process.cwd(), 'src/styles/app.css'),
      'utf8',
    )
    const bodyRule = stylesheet.match(/body\s*{([^}]*)}/)?.[1]

    expect(bodyRule).toBeDefined()
    expect(bodyRule).not.toMatch(/min-width\s*:/)
  })

  it('constrains long authenticated email text and keeps a narrow layout rule', () => {
    const stylesheet = readFileSync(
      resolve(process.cwd(), 'src/styles/app.css'),
      'utf8',
    )

    expect(stylesheet).toMatch(/\.auth-email\s*{[^}]*max-width:[^}]*text-overflow:\s*ellipsis/s)
    expect(stylesheet).toMatch(/@media\s*\(max-width:\s*420px\)/)
    expect(stylesheet).toMatch(/\.auth-dialog\s*{[^}]*width:\s*min\(100%,\s*420px\)/s)
  })
})
