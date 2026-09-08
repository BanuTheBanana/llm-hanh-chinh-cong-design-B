import type { Conversation, CreateMessageInput, CreateMessageResponse, Message, User } from '../types/api'

type ErrorResponse = {
  error?: {
    code?: string
    message?: string
    request_id?: string
  }
}

export class ApiError extends Error {
  readonly status: number
  readonly code?: string
  readonly requestId?: string

  constructor(message: string, status: number, code?: string, requestId?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.requestId = requestId
  }
}

function getApiBaseUrl() {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/$/, '')
  if (!apiBaseUrl) {
    throw new Error('Thiếu VITE_API_BASE_URL. Hãy cấu hình URL của Core Backend.')
  }
  return apiBaseUrl
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  let response: Response
  try {
    response = await fetch(`${getApiBaseUrl()}${path}`, {
      ...options,
      credentials: 'include',
      headers,
    })
  } catch (requestError) {
    if (requestError instanceof DOMException && requestError.name === 'AbortError') throw requestError
    throw new Error(
      'Không kết nối được Core Backend. Hãy kiểm tra backend và cấu hình CORS.',
      { cause: requestError },
    )
  }

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ErrorResponse | null
    throw new ApiError(
      body?.error?.message ?? 'Core Backend trả về lỗi.',
      response.status,
      body?.error?.code,
      body?.error?.request_id,
    )
  }

  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

const conversationPath = (conversationId: string) =>
  `/conversations/${encodeURIComponent(conversationId)}`

export const getCurrentUser = () => request<User>('/auth/me')
export const login = (displayName: string) =>
  request<User>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ display_name: displayName }),
  })
export const logout = () => request<void>('/auth/logout', { method: 'POST' })
export const getConversations = () => request<Conversation[]>('/conversations')
export const createConversation = () =>
  request<Conversation>('/conversations', { method: 'POST', body: JSON.stringify({}) })
export const getMessages = (conversationId: string, signal?: AbortSignal) =>
  request<Message[]>(`${conversationPath(conversationId)}/messages`, { signal })
export const createMessage = (conversationId: string, input: CreateMessageInput) =>
  request<CreateMessageResponse>(`${conversationPath(conversationId)}/messages`, {
    method: 'POST',
    body: JSON.stringify(input),
  })
