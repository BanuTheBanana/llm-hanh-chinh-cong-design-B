import type { Conversation, CreateMessageInput, CreateMessageResponse, Message, User } from '../types/api'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message: string, public status: number, public code?: string) { super(message); this.name = 'ApiError' }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  if (!apiBaseUrl) throw new Error('Thiếu VITE_API_BASE_URL. Hãy cấu hình URL của Core Backend.')
  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}${path}`, { ...options, credentials: 'include', headers: { 'Content-Type': 'application/json', ...options?.headers } })
  } catch {
    throw new Error(`Không kết nối được Core Backend tại ${apiBaseUrl}. Hãy kiểm tra backend và CORS.`)
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { error?: { code?: string; message?: string } } | null
    throw new ApiError(body?.error?.message ?? 'Core Backend trả về lỗi.', response.status, body?.error?.code)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const getCurrentUser = () => request<User>('/auth/me')
export const login = (display_name: string) => request<User>('/auth/login', { method: 'POST', body: JSON.stringify({ display_name }) })
export const logout = () => request<void>('/auth/logout', { method: 'POST' })
export const getConversations = () => request<Conversation[]>('/conversations')
export const createConversation = () => request<Conversation>('/conversations', { method: 'POST', body: JSON.stringify({}) })
export const getMessages = (conversationId: string) => request<Message[]>(`/conversations/${conversationId}/messages`)
export const createMessage = (conversationId: string, input: CreateMessageInput) => request<CreateMessageResponse>(`/conversations/${conversationId}/messages`, { method: 'POST', body: JSON.stringify(input) })