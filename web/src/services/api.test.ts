import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, getCurrentUser, login, putMessageFeedback, resolveApiBaseUrl } from './api'

describe('Core API client', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000/api/v1/')
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    fetchMock.mockReset()
  })

  it('keeps the API cookie on the same loopback hostname as the opened page', () => {
    expect(
      resolveApiBaseUrl('http://localhost:8005/api/v1/', 'http://127.0.0.1:3005/'),
    ).toBe('http://127.0.0.1:8005/api/v1')
    expect(
      resolveApiBaseUrl('https://api.example.vn/api/v1/', 'https://portal.example.vn/'),
    ).toBe('https://api.example.vn/api/v1')
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

  it('sends both feedback axes with PUT and credentials', async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          id: 'feedback-1',
          message_id: 'assistant-1',
          relevance: 'relevant',
          satisfaction: 'satisfied',
          created_at: '2026-09-13T01:00:00Z',
          updated_at: '2026-09-13T01:00:00Z',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    await putMessageFeedback('assistant-1', {
      relevance: 'relevant',
      satisfaction: 'satisfied',
      reason: null,
    })

    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('http://localhost:8000/api/v1/messages/assistant-1/feedback')
    expect(options.method).toBe('PUT')
    expect(options.credentials).toBe('include')
    expect(options.body).toBe(
      JSON.stringify({ relevance: 'relevant', satisfaction: 'satisfied', reason: null }),
    )
  })
})
