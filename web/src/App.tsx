import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import './App.css'
import {
  ApiError,
  createConversation,
  createMessage,
  getConversations,
  getCurrentUser,
  getMessages,
  login,
  logout,
} from './services/api'
import type { Conversation, Grounding, Message, User } from './types/api'

type BusyAction = 'login' | 'create-conversation' | 'send-message' | 'logout' | null
type ErrorKind = 'unauthorized' | 'api' | 'ai-timeout' | ''
type RetryTurn = {
  clientMessageId: string
  content: string
  conversationId: string
}

const ACTIVE_CONVERSATION_KEY = 'g1-active-conversation-id'
const UNAUTHORIZED_MESSAGE = 'Phiên đăng nhập không hợp lệ hoặc đã hết hạn. Vui lòng đăng nhập lại.'
const APP_STAGE = import.meta.env.VITE_APP_STAGE?.trim().toUpperCase() || 'G1'
const STAGE_LABEL =
  APP_STAGE === 'G5'
    ? 'G5 / QWEN + HYBRID + MCP'
    : APP_STAGE === 'G4'
    ? 'G4 / KIỂM CHỨNG EVIDENCE'
    : APP_STAGE === 'G3'
      ? 'G3 / LOCAL QWEN'
      : APP_STAGE === 'G2'
        ? 'G2 / SYNTHETIC RAG'
        : 'G1 / SYSTEM SMOKE'

function App() {
  const [user, setUser] = useState<User | null>(null)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [displayName, setDisplayName] = useState('')
  const [messageDraft, setMessageDraft] = useState('')
  const [retryTurn, setRetryTurn] = useState<RetryTurn | null>(null)
  const [loadingSession, setLoadingSession] = useState(true)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [busyAction, setBusyAction] = useState<BusyAction>(null)
  const [error, setError] = useState('')
  const [errorKind, setErrorKind] = useState<ErrorKind>('')

  const activeConversationIdRef = useRef<string | null>(null)
  const loadVersionRef = useRef(0)
  const messagesEndRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    let cancelled = false

    async function restoreSession() {
      try {
        const currentUser = await getCurrentUser()
        const availableConversations = await getConversations()
        if (cancelled) return

        setUser(currentUser)
        setConversations(availableConversations)

        const rememberedId = sessionStorage.getItem(ACTIVE_CONVERSATION_KEY)
        const rememberedConversation = availableConversations.find(({ id }) => id === rememberedId)
        if (!rememberedConversation) {
          sessionStorage.removeItem(ACTIVE_CONVERSATION_KEY)
          return
        }

        activeConversationIdRef.current = rememberedConversation.id
        setActiveConversation(rememberedConversation)
        setLoadingMessages(true)
        const history = await getMessages(rememberedConversation.id)
        if (!cancelled && activeConversationIdRef.current === rememberedConversation.id) {
          setMessages(history)
        }
      } catch (requestError) {
        if (cancelled) return
        if (isUnauthorized(requestError)) {
          activeConversationIdRef.current = null
          sessionStorage.removeItem(ACTIVE_CONVERSATION_KEY)
          setUser(null)
          setConversations([])
          setActiveConversation(null)
          setMessages([])
          setRetryTurn(null)
          setErrorKind('unauthorized')
          setError(UNAUTHORIZED_MESSAGE)
        } else {
          setErrorKind('api')
          setError(getErrorMessage(requestError))
        }
      } finally {
        if (!cancelled) {
          setLoadingSession(false)
          setLoadingMessages(false)
        }
      }
    }

    void restoreSession()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView?.({ block: 'end' })
  }, [messages, loadingMessages])

  function clearWorkspace() {
    loadVersionRef.current += 1
    activeConversationIdRef.current = null
    sessionStorage.removeItem(ACTIVE_CONVERSATION_KEY)
    setUser(null)
    setConversations([])
    setActiveConversation(null)
    setMessages([])
    setMessageDraft('')
    setRetryTurn(null)
    setLoadingMessages(false)
  }

  function showRequestError(requestError: unknown) {
    if (isUnauthorized(requestError)) {
      clearWorkspace()
      setErrorKind('unauthorized')
      setError(UNAUTHORIZED_MESSAGE)
      return
    }

    setErrorKind(isAiTimeout(requestError) ? 'ai-timeout' : 'api')
    setError(getErrorMessage(requestError))
  }

  function clearError() {
    setError('')
    setErrorKind('')
  }

  async function loadConversationMessages(
    conversationId: string,
    options: { clearBeforeLoad?: boolean; reportError?: boolean } = {},
  ) {
    const loadVersion = ++loadVersionRef.current
    if (options.clearBeforeLoad) setMessages([])
    setLoadingMessages(true)

    try {
      const history = await getMessages(conversationId)
      if (
        loadVersion === loadVersionRef.current &&
        activeConversationIdRef.current === conversationId
      ) {
        setMessages(history)
      }
      return history
    } catch (requestError) {
      if (
        loadVersion === loadVersionRef.current &&
        activeConversationIdRef.current === conversationId
      ) {
        if (isUnauthorized(requestError) || options.reportError !== false) {
          showRequestError(requestError)
        }
      }
      return null
    } finally {
      if (loadVersion === loadVersionRef.current) setLoadingMessages(false)
    }
  }

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalizedDisplayName = displayName.trim()
    if (!normalizedDisplayName || busyAction) return

    setBusyAction('login')
    clearError()
    try {
      const loggedInUser = await login(normalizedDisplayName)
      const availableConversations = await getConversations()
      sessionStorage.removeItem(ACTIVE_CONVERSATION_KEY)
      setUser(loggedInUser)
      setConversations(availableConversations)
      setActiveConversation(null)
      activeConversationIdRef.current = null
      setMessages([])
      setDisplayName('')
    } catch (requestError) {
      showRequestError(requestError)
    } finally {
      setBusyAction(null)
    }
  }

  async function handleSelectConversation(conversation: Conversation) {
    if (busyAction) return

    activeConversationIdRef.current = conversation.id
    sessionStorage.setItem(ACTIVE_CONVERSATION_KEY, conversation.id)
    setActiveConversation(conversation)
    setMessageDraft('')
    setRetryTurn(null)
    clearError()
    await loadConversationMessages(conversation.id, { clearBeforeLoad: true })
  }

  async function handleNewConversation() {
    if (busyAction) return

    setBusyAction('create-conversation')
    clearError()
    try {
      const conversation = await createConversation()
      loadVersionRef.current += 1
      activeConversationIdRef.current = conversation.id
      sessionStorage.setItem(ACTIVE_CONVERSATION_KEY, conversation.id)
      setConversations((current) => [conversation, ...current])
      setActiveConversation(conversation)
      setMessages([])
      setMessageDraft('')
      setRetryTurn(null)
    } catch (requestError) {
      showRequestError(requestError)
    } finally {
      setBusyAction(null)
    }
  }

  async function handleSendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await sendMessage()
  }

  async function sendMessage() {
    const conversation = activeConversation
    const content = messageDraft.trim()
    if (!conversation || !content || busyAction) return

    const existingRetry =
      retryTurn?.conversationId === conversation.id && retryTurn.content === content
        ? retryTurn
        : null
    const attempt: RetryTurn =
      existingRetry ?? {
        clientMessageId: crypto.randomUUID(),
        content,
        conversationId: conversation.id,
      }
    const existingFailedMessage = existingRetry
      ? [...messages]
          .reverse()
          .find(
            (message) =>
              message.role === 'user' && message.status === 'failed' && message.content === content,
          )
      : undefined
    const optimisticId = existingFailedMessage?.id ?? `pending:${attempt.clientMessageId}`
    const optimisticMessage: Message = {
      id: optimisticId,
      conversation_id: conversation.id,
      role: 'user',
      content,
      status: 'pending',
      created_at: existingFailedMessage?.created_at ?? new Date().toISOString(),
    }

    setRetryTurn(attempt)
    setBusyAction('send-message')
    clearError()
    setMessages((current) => {
      if (existingFailedMessage) {
        return current.map((message) =>
          message.id === existingFailedMessage.id ? optimisticMessage : message,
        )
      }
      return [...current.filter(({ id }) => id !== optimisticId), optimisticMessage]
    })

    try {
      const response = await createMessage(conversation.id, {
        client_message_id: attempt.clientMessageId,
        content,
      })

      if (activeConversationIdRef.current === conversation.id) {
        setMessages((current) => [
          ...current.filter(({ id }) => id !== optimisticId),
          response.user_message,
          response.assistant_message,
        ])
        setMessageDraft('')
        setRetryTurn(null)
        setConversations((current) =>
          current
            .map((item) =>
              item.id === conversation.id
                ? { ...item, updated_at: response.assistant_message.created_at }
                : item,
            )
            .sort((left, right) => right.updated_at.localeCompare(left.updated_at)),
        )
      }

      // Backend remains the source of truth. Re-read history instead of trusting only local state.
      await loadConversationMessages(conversation.id, { reportError: false })
    } catch (requestError) {
      if (activeConversationIdRef.current === conversation.id) {
        setMessages((current) =>
          current.map((message) =>
            message.id === optimisticId ? { ...message, status: 'failed' } : message,
          ),
        )
        showRequestError(requestError)
      }

      // The Core API stores the user message before calling AI. Load that durable state after failure.
      await loadConversationMessages(conversation.id, { reportError: false })
    } finally {
      setBusyAction(null)
    }
  }

  async function handleLogout() {
    if (busyAction) return

    setBusyAction('logout')
    clearError()
    let logoutError: unknown = null
    try {
      await logout()
    } catch (requestError) {
      if (!isUnauthorized(requestError)) logoutError = requestError
    } finally {
      clearWorkspace()
      setBusyAction(null)
    }

    if (logoutError) {
      setErrorKind('api')
      setError(
        `Đã xóa dữ liệu khỏi giao diện nhưng chưa xác nhận được phiên trên máy chủ: ${getErrorMessage(logoutError)}`,
      )
    }
  }

  function handleDraftChange(value: string) {
    setMessageDraft(value)
    if (retryTurn && value.trim() !== retryTurn.content) {
      setRetryTurn(null)
      if (errorKind === 'ai-timeout') clearError()
    }
  }

  if (loadingSession) {
    return <main className="status-screen">Đang kiểm tra phiên đăng nhập...</main>
  }

  if (!user) {
    return (
      <main className="login-screen">
        <section className="login-panel">
          <p className="eyebrow">{STAGE_LABEL}</p>
          <h1>Trợ lý hành chính</h1>
          <p className="intro">Đăng nhập demo để bắt đầu một cuộc hội thoại.</p>
          <form onSubmit={handleLogin} className="login-form">
            <label htmlFor="display-name">Tên hiển thị</label>
            <input
              id="display-name"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder="Ví dụ: Tú"
              autoComplete="name"
              maxLength={100}
              disabled={busyAction === 'login'}
            />
            <button type="submit" disabled={busyAction === 'login' || !displayName.trim()}>
              {busyAction === 'login' ? 'Đang đăng nhập...' : 'Đăng nhập'}
            </button>
          </form>
          {error && <StatusBanner kind={errorKind} message={error} />}
        </section>
      </main>
    )
  }

  const retryAvailable = Boolean(
    retryTurn &&
      activeConversation &&
      retryTurn.conversationId === activeConversation.id &&
      retryTurn.content === messageDraft.trim(),
  )

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <p className="eyebrow">{APP_STAGE} / WORKSPACE</p>
          <h1>Hành chính</h1>
        </div>
        <button
          className="new-conversation"
          type="button"
          onClick={handleNewConversation}
          disabled={busyAction !== null}
        >
          <span aria-hidden="true">+</span> Cuộc trò chuyện mới
        </button>
        <div className="conversation-list" aria-label="Danh sách cuộc trò chuyện">
          {conversations.length === 0 ? (
            <p className="muted">Chưa có cuộc trò chuyện nào.</p>
          ) : (
            conversations.map((conversation) => (
              <button
                className={activeConversation?.id === conversation.id ? 'conversation active' : 'conversation'}
                type="button"
                key={conversation.id}
                onClick={() => void handleSelectConversation(conversation)}
                disabled={busyAction !== null}
              >
                <span>{conversation.title}</span>
                <small>{formatDate(conversation.updated_at)}</small>
              </button>
            ))
          )}
        </div>
        <div className="account-block">
          <span className="avatar">{user.display_name.charAt(0).toUpperCase()}</span>
          <span className="account-name">{user.display_name}</span>
          <button
            className="logout-button"
            type="button"
            onClick={() => void handleLogout()}
            disabled={busyAction !== null}
            aria-label="Đăng xuất"
            title="Đăng xuất"
          >
            ↗
          </button>
        </div>
      </aside>
      <section className="chat-panel">
        <header className="chat-header">
          <div>
            <p className="eyebrow">CONVERSATION</p>
            <h2>{activeConversation?.title ?? 'Chọn một cuộc trò chuyện'}</h2>
          </div>
          <span className="connection-status">
            <i aria-hidden="true" /> Core Backend
          </span>
        </header>
        <div className="alert-slot">
          {error && (
            <StatusBanner
              kind={errorKind}
              message={error}
              onRetry={retryAvailable ? () => void sendMessage() : undefined}
            />
          )}
        </div>
        <div className="messages" aria-live="polite" aria-busy={loadingMessages}>
          {!activeConversation ? (
            <EmptyState
              mark="01"
              title="Bắt đầu từ một cuộc trò chuyện mới"
              description="Tạo hoặc chọn một cuộc trò chuyện để tải lịch sử từ Core Backend."
            />
          ) : loadingMessages ? (
            <div className="messages-loading" role="status">Đang tải lịch sử...</div>
          ) : messages.length === 0 ? (
            <EmptyState
              mark="02"
              title="Cuộc trò chuyện đang trống"
              description={`Gửi một tin nhắn đầu tiên để kiểm tra hệ thống ${APP_STAGE}.`}
            />
          ) : (
            messages.map((message) => (
              <article className={`message ${message.role} ${message.status}`} key={message.id}>
                <div className="message-meta">
                  {message.role === 'user'
                    ? user.display_name
                    : message.grounding
                      ? 'Trợ lý có nguồn'
                      : 'Mock AI'}
                  {message.status !== 'completed' && (
                    <span className="message-status">
                      {message.status === 'pending' ? 'Đang xử lý' : 'Gửi chưa hoàn tất'}
                    </span>
                  )}
                </div>
                <p>{message.content}</p>
                {message.role === 'assistant' && message.grounding && (
                  <GroundingPanel grounding={message.grounding} />
                )}
              </article>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>
        <form className="composer" onSubmit={handleSendMessage}>
          <textarea
            value={messageDraft}
            onChange={(event) => handleDraftChange(event.target.value)}
            placeholder={
              activeConversation
                ? 'Viết tin nhắn kiểm thử...'
                : 'Tạo hoặc chọn một cuộc trò chuyện trước'
            }
            disabled={!activeConversation || busyAction !== null}
            maxLength={4_000}
            rows={2}
          />
          <button
            type="submit"
            disabled={!activeConversation || !messageDraft.trim() || busyAction !== null}
          >
            {busyAction === 'send-message' ? 'Đang gửi...' : 'Gửi'}
          </button>
        </form>
      </section>
    </main>
  )
}

function EmptyState({ mark, title, description }: { mark: string; title: string; description: string }) {
  return (
    <div className="empty-state">
      <span className="empty-mark">{mark}</span>
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  )
}

function GroundingPanel({ grounding }: { grounding: Grounding }) {
  const label =
    grounding.status === 'ANSWER'
      ? 'Đã đối chiếu nguồn'
      : grounding.status === 'NEED_CLARIFICATION'
        ? 'Cần làm rõ'
        : 'Chưa đủ dữ liệu'

  return (
    <section className={`grounding grounding-${grounding.status.toLowerCase()}`}>
      <div className="grounding-heading">
        <strong>{label}</strong>
        <span>{grounding.sources.length} nguồn</span>
      </div>
      {grounding.data_classification === 'D0_SYSTEM_SMOKE' && (
        <small className="grounding-demo">Dữ liệu mô phỏng D0 — không phải hướng dẫn thực tế.</small>
      )}
      {grounding.data_classification === 'D2_COMPANY_REAL' && (
        <small className="grounding-demo">Nguồn nội bộ đã duyệt cho demo.</small>
      )}
      {grounding.verification && grounding.status === 'ANSWER' && (
        <small className="grounding-demo">
          {grounding.verification.fallback_used
            ? 'Trích xuất nguyên văn: câu trả lời của model chưa qua kiểm tra đầy đủ.'
            : 'Nội dung được dựng từ evidence, giữ nguyên các điều kiện trong nguồn.'}
        </small>
      )}
      {grounding.knowledge_version && (
        <small className="grounding-version">
          Phiên bản cập nhật: <code>{grounding.knowledge_version}</code>
          {grounding.source_checked_at
            ? ` · duyệt ${new Intl.DateTimeFormat('vi-VN').format(new Date(grounding.source_checked_at))}`
            : ''}
        </small>
      )}
      {grounding.checklist && grounding.checklist.length > 0 && (
        <dl className="answer-checklist" aria-label="Nội dung đã kiểm chứng">
          {grounding.checklist.map((item) => (
            <div key={`${item.field}:${item.evidence_ids.join(':')}`}>
              <dt>{item.label}</dt>
              <dd>{item.value}</dd>
            </div>
          ))}
        </dl>
      )}
      {grounding.sources.length > 0 && (
        <ol className="source-list" aria-label="Nguồn tham chiếu">
          {grounding.sources.map((source) => {
            const href = safeSourceUrl(source.url)
            return (
              <li key={`${source.source_id}:${source.fragment_id}`}>
                {href ? (
                  <a href={href} target="_blank" rel="noreferrer noopener">
                    {source.title}
                  </a>
                ) : (
                  <span>{source.title}</span>
                )}
                <code>{source.fragment_id}</code>
              </li>
            )
          })}
        </ol>
      )}
      {grounding.missing_information.length > 0 && (
        <div className="missing-information">
          <span>Cần bổ sung:</span>
          <ul>
            {grounding.missing_information.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

function safeSourceUrl(value: string | null) {
  if (!value) return null
  try {
    const url = new URL(value)
    return url.protocol === 'https:' ? url.toString() : null
  } catch {
    return null
  }
}

function getErrorMessage(requestError: unknown) {
  if (requestError instanceof ApiError) return requestError.message
  return requestError instanceof Error ? requestError.message : 'Không thể kết nối Core Backend.'
}

function isUnauthorized(requestError: unknown) {
  return requestError instanceof ApiError && requestError.status === 401
}

function isAiTimeout(requestError: unknown) {
  return (
    requestError instanceof ApiError &&
    (requestError.status === 408 ||
      requestError.status === 504 ||
      requestError.code === 'AI_SERVICE_TIMEOUT' ||
      requestError.message.toLowerCase().includes('timeout'))
  )
}

function StatusBanner({
  kind,
  message,
  onRetry,
}: {
  kind: ErrorKind
  message: string
  onRetry?: () => void
}) {
  const label = kind === 'unauthorized' ? 'PHIÊN ĐĂNG NHẬP' : kind === 'ai-timeout' ? 'AI TIMEOUT' : 'LỖI API'
  return (
    <div className="error-banner" role="alert">
      <span>
        <strong>{label}</strong> {message}
      </span>
      {onRetry && (
        <button type="button" onClick={onRetry}>
          Thử lại
        </button>
      )}
    </div>
  )
}

function formatDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '--/--'
  return new Intl.DateTimeFormat('vi-VN', { day: '2-digit', month: '2-digit' }).format(date)
}

export default App
