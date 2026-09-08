import { FormEvent, useEffect, useState } from 'react'
import './App.css'
import { ApiError, createConversation, createMessage, getConversations, getCurrentUser, getMessages, login, logout } from './services/api'
import type { Conversation, Message, User } from './types/api'

const newClientMessageId = () => crypto.randomUUID()
const localAdminEnabled = import.meta.env.VITE_ENABLE_LOCAL_ADMIN_BYPASS === 'true'
const localUsers: Record<string, User> = {
  admin: { id: 'local-admin', display_name: 'admin' },
  admin2: { id: 'local-admin-2', display_name: 'admin2' },
}

const localStorageKey = (userId: string, resource: string) => `g1-local-${userId}-${resource}`

function readLocalData<T>(key: string, fallback: T): T {
  try {
    return JSON.parse(localStorage.getItem(key) ?? JSON.stringify(fallback)) as T
  } catch {
    return fallback
  }
}

function writeLocalData<T>(key: string, value: T) {
  localStorage.setItem(key, JSON.stringify(value))
}

function App() {
  const [user, setUser] = useState<User | null>(null)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [displayName, setDisplayName] = useState('')
  const [messageDraft, setMessageDraft] = useState('')
  const [clientMessageId, setClientMessageId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState('')
  const [errorKind, setErrorKind] = useState<'unauthorized' | 'api' | 'ai-timeout' | ''>('')
  const isLocalUser = user?.id === 'local-admin' || user?.id === 'local-admin-2'

  useEffect(() => {
    if (localAdminEnabled) {
      setLoading(false)
      return
    }

    getCurrentUser()
      .then((currentUser) => {
        setUser(currentUser)
        return getConversations()
      })
      .then(setConversations)
      .catch((requestError: unknown) => {
        if (requestError instanceof ApiError && requestError.status === 401) {
          setErrorKind('unauthorized')
          setError('Phiên đăng nhập không hợp lệ hoặc đã hết hạn. Vui lòng đăng nhập lại.')
        } else setError(getErrorMessage(requestError))
      })
      .finally(() => setLoading(false))
  }, [])

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!displayName.trim()) return
    setWorking(true)
    setError('')
    setErrorKind('')
    try {
      const localUser = localUsers[displayName.trim().toLowerCase()]
      if (localAdminEnabled && localUser) {
        setUser(localUser)
        setConversations(readLocalData<Conversation[]>(localStorageKey(localUser.id, 'conversations'), []))
        return
      }
      const loggedInUser = await login(displayName.trim())
      if (!loggedInUser?.id || !loggedInUser.display_name) {
        throw new Error('Core Backend trả về dữ liệu đăng nhập không hợp lệ.')
      }
      setUser(loggedInUser)
      setConversations(await getConversations())
    } catch (requestError) {
      setErrorKind(requestError instanceof ApiError && requestError.status === 401 ? 'unauthorized' : 'api')
      setError(getErrorMessage(requestError))
    } finally {
      setWorking(false)
    }
  }

  async function handleSelectConversation(conversation: Conversation) {
    setActiveConversation(conversation)
    setError('')
    setErrorKind('')
    try {
      if (isLocalUser) {
        const storedMessages = readLocalData<Record<string, Message[]>>(localStorageKey(user?.id ?? '', 'messages'), {})
        setMessages(storedMessages[conversation.id] ?? [])
        return
      }
      setMessages(await getMessages(conversation.id))
    } catch (requestError) {
      setError(getErrorMessage(requestError))
    }
  }

  async function handleNewConversation() {
    setWorking(true)
    setError('')
    setErrorKind('')
    try {
      if (isLocalUser) {
        const now = new Date().toISOString()
        const conversation: Conversation = { id: crypto.randomUUID(), title: 'Cuộc trò chuyện mới', created_at: now, updated_at: now }
        const nextConversations = [conversation, ...conversations]
        writeLocalData(localStorageKey(user?.id ?? '', 'conversations'), nextConversations)
        setConversations(nextConversations)
        setActiveConversation(conversation)
        setMessages([])
        return
      }
      const conversation = await createConversation()
      setConversations((current) => [conversation, ...current])
      setActiveConversation(conversation)
      setMessages([])
    } catch (requestError) {
      setError(getErrorMessage(requestError))
    } finally {
      setWorking(false)
    }
  }

  async function handleSendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await sendMessage()
  }

  async function sendMessage() {
    const content = messageDraft.trim()
    if (!activeConversation || !content || working) return
    setWorking(true)
    setError('')
    setErrorKind('')
    try {
      if (isLocalUser) {
        const now = new Date().toISOString()
        const userMessage: Message = { id: crypto.randomUUID(), conversation_id: activeConversation.id, role: 'user', content, status: 'completed', created_at: now }
        const assistantMessage: Message = { id: crypto.randomUUID(), conversation_id: activeConversation.id, role: 'assistant', content: 'Đây là phản hồi local để kiểm thử giao diện G1.', status: 'completed', created_at: now }
        const nextMessages = [...messages, userMessage, assistantMessage]
        const storedMessages = readLocalData<Record<string, Message[]>>(localStorageKey(user?.id ?? '', 'messages'), {})
        writeLocalData(localStorageKey(user?.id ?? '', 'messages'), { ...storedMessages, [activeConversation.id]: nextMessages })
        setMessages(nextMessages)
        setMessageDraft('')
        setClientMessageId(null)
        return
      }
      const response = await createMessage(activeConversation.id, {
        client_message_id: clientMessageId ?? newClientMessageId(),
        content,
      })
      setMessages((current) => [...current, response.user_message, response.assistant_message])
      setMessageDraft('')
      setClientMessageId(null)
    } catch (requestError) {
      if (!clientMessageId) setClientMessageId(newClientMessageId())
      setErrorKind(isAiTimeout(requestError) ? 'ai-timeout' : requestError instanceof ApiError && requestError.status === 401 ? 'unauthorized' : 'api')
      setError(getErrorMessage(requestError))
    } finally {
      setWorking(false)
    }
  }

  async function handleLogout() {
    if (isLocalUser) {
      setUser(null)
      setConversations([])
      setActiveConversation(null)
      setMessages([])
      setMessageDraft('')
      setClientMessageId(null)
      setError('')
      setErrorKind('')
      return
    }
    await logout()
    setUser(null)
    setConversations([])
    setActiveConversation(null)
    setMessages([])
    setMessageDraft('')
    setClientMessageId(null)
    setError('')
    setErrorKind('')
  }

  if (loading) return <main className="status-screen">Đang kiểm tra phiên đăng nhập...</main>

  if (!user) {
    return (
      <main className="login-screen">
        <section className="login-panel">
          <p className="eyebrow">G1 / SYSTEM SMOKE</p>
          <h1>Trợ lý hành chính</h1>
          <p className="intro">Đăng nhập demo để bắt đầu một cuộc hội thoại.</p>
          {localAdminEnabled && <p className="local-mode" role="status">Local test mode đang bật. Dùng tên <strong>admin</strong> hoặc <strong>admin2</strong>. Hai tài khoản có history riêng.</p>}
          <form onSubmit={handleLogin} className="login-form">
            <label htmlFor="display-name">Tên hiển thị</label>
            <input id="display-name" value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="Ví dụ: Tú" autoComplete="name" disabled={working} />
            <button type="submit" disabled={working || !displayName.trim()}>{working ? 'Đang đăng nhập...' : 'Đăng nhập'}</button>
          </form>
          {error && <StatusBanner kind={errorKind} message={error} onRetry={() => window.location.reload()} />}
        </section>
      </main>
    )
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-block"><p className="eyebrow">G1 / WORKSPACE</p><h1>Hành chính</h1></div>
        <button className="new-conversation" type="button" onClick={handleNewConversation} disabled={working}><span aria-hidden="true">+</span> Cuộc trò chuyện mới</button>
        <div className="conversation-list">
          {conversations.length === 0 ? <p className="muted">Chưa có cuộc trò chuyện nào.</p> : conversations.map((conversation) => (
            <button className={activeConversation?.id === conversation.id ? 'conversation active' : 'conversation'} type="button" key={conversation.id} onClick={() => handleSelectConversation(conversation)}>
              <span>{conversation.title}</span><small>{formatDate(conversation.updated_at)}</small>
            </button>
          ))}
        </div>
        <div className="account-block"><span className="avatar">{user.display_name.charAt(0).toUpperCase()}</span><span className="account-name">{user.display_name}</span><button className="logout-button" type="button" onClick={handleLogout} title="Đăng xuất">↗</button></div>
      </aside>
      <section className="chat-panel">
        <header className="chat-header"><div><p className="eyebrow">CONVERSATION</p><h2>{activeConversation?.title ?? 'Chọn một cuộc trò chuyện'}</h2></div><span className="connection-status"><i /> {isLocalUser ? 'Local admin mode' : 'Core Backend'}</span></header>
        {error && <StatusBanner kind={errorKind} message={error} onRetry={messageDraft.trim() ? sendMessage : undefined} />}
        <div className="messages" aria-live="polite">
          {!activeConversation ? <div className="empty-state"><span className="empty-mark">01</span><h3>Bắt đầu từ một cuộc trò chuyện mới</h3><p>Lịch sử sẽ được tải từ Core Backend sau khi bạn chọn conversation.</p></div> : messages.length === 0 ? <div className="empty-state"><span className="empty-mark">02</span><h3>Cuộc trò chuyện đang trống</h3><p>Gửi một tin nhắn đầu tiên để kiểm tra đường ống G1.</p></div> : messages.map((message) => <article className={`message ${message.role}`} key={message.id}><div className="message-meta">{message.role === 'user' ? user.display_name : 'Mock AI'}</div><p>{message.content}</p></article>)}
        </div>
        <form className="composer" onSubmit={handleSendMessage}><textarea value={messageDraft} onChange={(event) => { setMessageDraft(event.target.value); if (!event.target.value.trim()) setClientMessageId(null) }} placeholder={activeConversation ? 'Viết tin nhắn kiểm thử...' : 'Tạo hoặc chọn một cuộc trò chuyện trước'} disabled={!activeConversation || working} rows={2} /><button type="submit" disabled={!activeConversation || !messageDraft.trim() || working}>{working ? 'Đang gửi...' : 'Gửi'}</button></form>
      </section>
    </main>
  )
}

function getErrorMessage(error: unknown) {
  if (error instanceof ApiError) return error.message
  return error instanceof Error ? error.message : 'Không thể kết nối Core Backend.'
}

function isAiTimeout(error: unknown) {
  return error instanceof ApiError && (error.status === 408 || error.status === 504 || error.code === 'AI_SERVICE_TIMEOUT' || error.message.toLowerCase().includes('timeout'))
}

function StatusBanner({ kind, message, onRetry }: { kind: 'unauthorized' | 'api' | 'ai-timeout' | ''; message: string; onRetry?: () => void }) {
  const label = kind === 'unauthorized' ? 'UNAUTHORIZED' : kind === 'ai-timeout' ? 'AI TIMEOUT' : 'API ERROR'
  return <div className="error-banner login-error" role="alert"><span><strong>{label}</strong> {message}</span>{onRetry && <button type="button" onClick={onRetry}>Thử lại</button>}</div>
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('vi-VN', { day: '2-digit', month: '2-digit' }).format(new Date(value))
}

export default App
