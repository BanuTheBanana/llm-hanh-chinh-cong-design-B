import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import * as api from './services/api'
import type { Conversation, CreateMessageResponse, Grounding, Message, User } from './types/api'

vi.mock('./services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./services/api')>()
  return {
    ...actual,
    createConversation: vi.fn(),
    createMessage: vi.fn(),
    getConversations: vi.fn(),
    getCurrentUser: vi.fn(),
    getMessages: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
  }
})

const currentUser: User = { id: 'user-1', display_name: 'Tú' }
const conversationA: Conversation = {
  id: 'conversation-a',
  title: 'Hồ sơ A',
  created_at: '2026-09-08T02:00:00Z',
  updated_at: '2026-09-08T02:00:00Z',
}
const conversationB: Conversation = {
  id: 'conversation-b',
  title: 'Hồ sơ B',
  created_at: '2026-09-08T03:00:00Z',
  updated_at: '2026-09-08T03:00:00Z',
}

const getCurrentUserMock = vi.mocked(api.getCurrentUser)
const getConversationsMock = vi.mocked(api.getConversations)
const getMessagesMock = vi.mocked(api.getMessages)
const createMessageMock = vi.mocked(api.createMessage)
const loginMock = vi.mocked(api.login)
const logoutMock = vi.mocked(api.logout)

function message(
  id: string,
  conversationId: string,
  role: Message['role'],
  content: string,
  status: Message['status'] = 'completed',
): Message {
  return {
    id,
    conversation_id: conversationId,
    role,
    content,
    status,
    created_at: '2026-09-08T04:00:00Z',
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

describe('G1 web flow', () => {
  beforeEach(() => {
    getCurrentUserMock.mockResolvedValue(currentUser)
    getConversationsMock.mockResolvedValue([])
    getMessagesMock.mockResolvedValue([])
    loginMock.mockResolvedValue(currentUser)
    logoutMock.mockResolvedValue(undefined)
  })

  it('shows login for an unauthenticated user and logs in through the Core API', async () => {
    getCurrentUserMock.mockRejectedValueOnce(new api.ApiError('Chưa đăng nhập.', 401, 'UNAUTHORIZED'))
    getConversationsMock.mockResolvedValueOnce([])
    const user = userEvent.setup()

    render(<App />)

    await screen.findByRole('heading', { name: 'Trợ lý hành chính' })
    await user.type(screen.getByLabelText('Tên hiển thị'), '  Tú  ')
    await user.click(screen.getByRole('button', { name: 'Đăng nhập' }))

    await screen.findByText('Tú')
    expect(loginMock).toHaveBeenCalledWith('Tú')
    expect(getConversationsMock).toHaveBeenCalledOnce()
  })

  it('shows a pending turn, then reloads the authoritative message history', async () => {
    getConversationsMock.mockResolvedValue([conversationA])
    const generation = deferred<CreateMessageResponse>()
    const userMessage = message('user-message-1', conversationA.id, 'user', 'Xin chào')
    const assistantMessage = message('assistant-message-1', conversationA.id, 'assistant', 'Phản hồi mock')
    getMessagesMock.mockResolvedValueOnce([]).mockResolvedValueOnce([userMessage, assistantMessage])
    createMessageMock.mockReturnValueOnce(generation.promise)
    const user = userEvent.setup()

    render(<App />)
    await user.click(await screen.findByRole('button', { name: /Hồ sơ A/ }))
    await user.type(screen.getByPlaceholderText('Viết tin nhắn kiểm thử...'), 'Xin chào')
    await user.click(screen.getByRole('button', { name: 'Gửi' }))

    expect(await screen.findByText('Đang xử lý')).toBeInTheDocument()
    const request = createMessageMock.mock.calls[0][1]
    expect(request.client_message_id).toMatch(/^[0-9a-f-]{36}$/i)

    await act(async () => generation.resolve({ user_message: userMessage, assistant_message: assistantMessage }))

    expect(await screen.findByText('Phản hồi mock')).toBeInTheDocument()
    expect(getMessagesMock).toHaveBeenLastCalledWith(conversationA.id)
    expect(screen.getByPlaceholderText('Viết tin nhắn kiểm thử...')).toHaveValue('')
  })

  it('reuses the exact idempotency key when retrying an AI timeout', async () => {
    getConversationsMock.mockResolvedValue([conversationA])
    const failedUserMessage = message('user-message-1', conversationA.id, 'user', 'Thử lại tôi', 'failed')
    const completedUserMessage = { ...failedUserMessage, status: 'completed' as const }
    const assistantMessage = message('assistant-message-1', conversationA.id, 'assistant', 'Đã thử lại')
    getMessagesMock
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([failedUserMessage])
      .mockResolvedValueOnce([completedUserMessage, assistantMessage])
    createMessageMock
      .mockRejectedValueOnce(new api.ApiError('AI đang phản hồi chậm.', 504, 'AI_SERVICE_TIMEOUT'))
      .mockResolvedValueOnce({ user_message: completedUserMessage, assistant_message: assistantMessage })
    const user = userEvent.setup()

    render(<App />)
    await user.click(await screen.findByRole('button', { name: /Hồ sơ A/ }))
    await user.type(screen.getByPlaceholderText('Viết tin nhắn kiểm thử...'), 'Thử lại tôi')
    await user.click(screen.getByRole('button', { name: 'Gửi' }))

    await screen.findByRole('button', { name: 'Thử lại' })
    const firstIdempotencyKey = createMessageMock.mock.calls[0][1].client_message_id
    await user.click(screen.getByRole('button', { name: 'Thử lại' }))

    expect(await screen.findByText('Đã thử lại')).toBeInTheDocument()
    expect(createMessageMock.mock.calls[1][1].client_message_id).toBe(firstIdempotencyKey)
    expect(screen.getAllByText('Thử lại tôi')).toHaveLength(1)
  })

  it('does not mix histories when older conversation requests finish last', async () => {
    getConversationsMock.mockResolvedValue([conversationA, conversationB])
    const historyA = deferred<Message[]>()
    const historyB = deferred<Message[]>()
    getMessagesMock.mockImplementation((conversationId) =>
      conversationId === conversationA.id ? historyA.promise : historyB.promise,
    )
    const user = userEvent.setup()

    render(<App />)
    await user.click(await screen.findByRole('button', { name: /Hồ sơ A/ }))
    await user.click(screen.getByRole('button', { name: /Hồ sơ B/ }))

    await act(async () => historyB.resolve([message('b-1', conversationB.id, 'assistant', 'Nội dung B')]))
    expect(await screen.findByText('Nội dung B')).toBeInTheDocument()

    await act(async () => historyA.resolve([message('a-1', conversationA.id, 'assistant', 'Nội dung A')]))
    await waitFor(() => expect(screen.queryByText('Nội dung A')).not.toBeInTheDocument())
    expect(screen.getByRole('heading', { name: 'Hồ sơ B' })).toBeInTheDocument()
  })

  it('returns to login and clears conversation data when a later request is unauthorized', async () => {
    getConversationsMock.mockResolvedValue([conversationA])
    getMessagesMock.mockRejectedValueOnce(new api.ApiError('Hết phiên.', 401, 'UNAUTHORIZED'))
    const user = userEvent.setup()

    render(<App />)
    await user.click(await screen.findByRole('button', { name: /Hồ sơ A/ }))

    expect(await screen.findByRole('heading', { name: 'Trợ lý hành chính' })).toBeInTheDocument()
    expect(screen.queryByText('Hồ sơ A')).not.toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Phiên đăng nhập')
  })

  it('clears local UI data even when server logout cannot be confirmed', async () => {
    getConversationsMock.mockResolvedValue([conversationA])
    logoutMock.mockRejectedValueOnce(new Error('Mất kết nối'))
    const user = userEvent.setup()

    render(<App />)
    await user.click(await screen.findByRole('button', { name: 'Đăng xuất' }))

    expect(await screen.findByRole('heading', { name: 'Trợ lý hành chính' })).toBeInTheDocument()
    expect(screen.queryByText('Hồ sơ A')).not.toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Đã xóa dữ liệu khỏi giao diện')
  })

  it.each([false, true])('renders sources and G4 extraction state (fallback=%s)', async (fallback) => {
    getConversationsMock.mockResolvedValue([conversationA])
    const grounding: Grounding = {
      request_id: '00000000-0000-4000-8000-000000000001',
      evidence_bundle_id: '10000000-0000-4000-8000-000000000001',
      status: 'ANSWER',
      corpus_version: 'fixture-v1',
      data_classification: 'D0_SYSTEM_SMOKE',
      prompt_version: 'g2-grounded-v2',
      provider: 'template',
      model: 'template-grounded-v2',
      missing_information: [],
      verification: {
        plan_version: 'g4-answer-plan-v1',
        policy: 'full-claim-exact-v1',
        candidate_checked: true,
        candidate_passed: !fallback,
        fallback_used: fallback,
        reasons: fallback ? ['FULL_CLAIM_TEXT_NOT_VERIFIED'] : [],
      },
      sources: [
        {
          fragment_id: 'frag_fees',
          source_id: 'src_synthetic',
          title: 'Nguồn fixture chính thức',
          url: 'https://fixture.invalid/synthetic',
          metadata: {},
        },
        {
          fragment_id: 'frag_bad',
          source_id: 'src_bad',
          title: 'Nguồn không an toàn',
          url: 'javascript:alert(1)',
          metadata: {},
        },
      ],
    }
    getMessagesMock.mockResolvedValue([
      message('u-1', conversationA.id, 'user', 'Lệ phí?'),
      { ...message('a-1', conversationA.id, 'assistant', 'Câu trả lời có nguồn'), grounding },
    ])
    const user = userEvent.setup()

    render(<App />)
    await user.click(await screen.findByRole('button', { name: /Hồ sơ A/ }))

    expect(await screen.findByText('Đã đối chiếu nguồn')).toBeInTheDocument()
    expect(screen.getByText(/Dữ liệu mô phỏng D0/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Nguồn fixture chính thức' })).toHaveAttribute(
      'href',
      'https://fixture.invalid/synthetic',
    )
    expect(screen.getByText('Nguồn không an toàn').closest('a')).toBeNull()
    expect(screen.getByText(fallback
      ? /Trích xuất nguyên văn: câu trả lời của model/
      : /Nội dung được dựng từ evidence/)).toBeInTheDocument()
  })

  it('renders a private reviewed D2 source without inventing a public link', async () => {
    getConversationsMock.mockResolvedValue([conversationA])
    const grounding: Grounding = {
      request_id: '00000000-0000-4000-8000-000000000002',
      evidence_bundle_id: '10000000-0000-4000-8000-000000000002',
      status: 'ANSWER',
      corpus_version: 'private-demo-v1',
      data_classification: 'D2_COMPANY_REAL',
      prompt_version: 'g2-grounded-v2',
      provider: 'local',
      model: 'Qwen3-1.7B',
      missing_information: [],
      sources: [
        {
          fragment_id: 'frag_private',
          source_id: 'src_private',
          title: 'Nguồn nội bộ đã duyệt',
          url: null,
          metadata: {},
        },
      ],
    }
    getMessagesMock.mockResolvedValue([
      message('u-2', conversationA.id, 'user', 'Câu hỏi thử'),
      { ...message('a-2', conversationA.id, 'assistant', 'Câu trả lời thử'), grounding },
    ])
    const user = userEvent.setup()

    render(<App />)
    await user.click(await screen.findByRole('button', { name: /Hồ sơ A/ }))

    expect(await screen.findByText('Nguồn nội bộ đã duyệt cho demo.')).toBeInTheDocument()
    expect(screen.getByText('Nguồn nội bộ đã duyệt').closest('a')).toBeNull()
  })
})
