import { describe, expect, it } from 'vitest'

import { sanitizeArtifactUrl } from './sanitizeArtifactUrl'

describe('sanitizeArtifactUrl', () => {
  it('gibt null für leere URL zurück', () => {
    expect(sanitizeArtifactUrl('')).toBeNull()
  })

  it('gibt null für URL nur mit Leerzeichen zurück', () => {
    expect(sanitizeArtifactUrl('   ')).toBeNull()
  })

  it('gibt null für protocol-relative URL zurück', () => {
    expect(sanitizeArtifactUrl('//evil.com/path')).toBeNull()
  })

  it('akzeptiert relative URL mit / am Anfang', () => {
    expect(sanitizeArtifactUrl('/v1/artifacts/abc')).toBe('/v1/artifacts/abc')
  })

  it('trimmt Leerzeichen bei relativer URL', () => {
    expect(sanitizeArtifactUrl('  /v1/artifacts/abc  ')).toBe('/v1/artifacts/abc')
  })

  it('akzeptiert absolute HTTP-URL', () => {
    const url = 'http://localhost:8000/v1/artifacts/abc'
    expect(sanitizeArtifactUrl(url)).toBe(url)
  })

  it('akzeptiert absolute HTTPS-URL', () => {
    const url = 'https://example.com/artifact.png'
    expect(sanitizeArtifactUrl(url)).toBe(url)
  })

  it('gibt null für javascript:-Protokoll zurück', () => {
    expect(sanitizeArtifactUrl('javascript:alert(1)')).toBeNull()
  })

  it('gibt null für data:-Protokoll zurück', () => {
    expect(sanitizeArtifactUrl('data:text/html,<h1>Hi</h1>')).toBeNull()
  })

  it('gibt null für file:-Protokoll zurück', () => {
    expect(sanitizeArtifactUrl('file:///etc/passwd')).toBeNull()
  })

  it('akzeptiert relative URL ohne Protokoll', () => {
    expect(sanitizeArtifactUrl('/favicon.svg')).toBe('/favicon.svg')
  })
})
