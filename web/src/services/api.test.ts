import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, getCurrentUser, login } from './api'

describe('Core API client', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000/api/v1/')
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    fetchMock.mockReset()
  })

  it('always sends cookies but does not force a JSON preflight header on GET', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ id: 'user-1', display_name: 'Tú' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    await getCurrentUser()

    expect(fetchMock).toHaveBeenCalledOnce()
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('http://localhost:8000/api/v1/auth/me')
    expect(options.credentials).toBe('include')
    expect(new Headers(options.headers).has('Content-Type')).toBe(false)
  })

  it('sends the login JSON using the frozen contract', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ id: 'user-1', display_name: 'Tú' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    await login('Tú')

    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('http://localhost:8000/api/v1/auth/login')
    expect(options.method).toBe('POST')
    expect(options.body).toBe(JSON.stringify({ display_name: 'Tú' }))
    expect(new Headers(options.headers).get('Content-Type')).toBe('application/json')
  })

  it('preserves the backend error code and request id', async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            code: 'AI_SERVICE_TIMEOUT',
            message: 'AI đang phản hồi chậm.',
            request_id: 'request-1',
          },
        }),
        { status: 504, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    const request = login('Tú')
    await expect(request).rejects.toMatchObject({
      status: 504,
      code: 'AI_SERVICE_TIMEOUT',
      requestId: 'request-1',
    } satisfies Partial<ApiError>)
  })
})
