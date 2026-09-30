import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { ArrowRight, BookOpenText, ChatCircleDots, CheckCircle, CircleNotch, MagnifyingGlass, Plus, SealCheck, WarningCircle } from '@phosphor-icons/react'
import { ask, getHealth, retrieve, type Citation, type EvidenceBundle, type GroundedAnswer, type Health, type Query } from './api/ragClient'

type Turn = {
  id: number
  query: string
  mode: 'answer' | 'retrieve'
  answer?: GroundedAnswer
  bundle?: EvidenceBundle
  error?: string
}

function Sources({ citations }: { citations: Citation[] }) {
  if (!citations.length) return null
  return <details className="source-panel">
    <summary><BookOpenText size={18} /> Nguồn trích dẫn <span>{citations.length}</span></summary>
    <div className="source-list">{citations.map((citation, index) =>
      <div className="source-item" key={`${citation.fragment_id}-${index}`}>
        <span className="source-index">{String(index + 1).padStart(2, '0')}</span>
        <div><p>{citation.claim_text}</p><small>Nguồn {citation.source_id} · Mảnh {citation.fragment_id}</small>
          <small>Vị trí nguồn: {citation.source_locator}</small></div>
      </div>)}</div>
  </details>
}

function AnswerView({ answer }: { answer: GroundedAnswer }) {
  if (answer.status === 'clarification_needed') {
    return <div className="reply clarification"><div className="reply-label"><ChatCircleDots size={17} /> Cần làm rõ</div>
      <p>{answer.clarification_prompt}</p></div>
  }
  if (answer.status === 'insufficient_data') {
    const message = answer.clarification_prompt?.trim() || answer.answer_text.trim() || 'Backend chưa có đủ dữ liệu để trả lời câu hỏi này.'
    return <div className="reply insufficient"><div className="reply-label"><WarningCircle size={17} /> Chưa đủ dữ liệu</div>
      <p>{message}</p></div>
  }
  return <div className="reply"><div className="reply-label"><SealCheck size={17} weight="fill" /> Trợ lý hành chính</div>
    <p className="reply-text">{answer.answer_text}</p><Sources citations={answer.citations} /></div>
}

function RetrievalView({ bundle }: { bundle: EvidenceBundle }) {
  return <div className="reply"><div className="reply-label"><MagnifyingGlass size={17} /> Kết quả truy xuất từ backend</div>
    <p className="retrieval-note">Trạng thái: {bundle.confidence_status}. Giao diện hiển thị nguyên kết quả truy xuất; chưa diễn giải thành tư vấn thủ tục.</p>
    {bundle.ambiguous_candidates?.length > 0 && <div className="candidate-list"><strong>Các ứng viên backend trả về</strong>
      {bundle.ambiguous_candidates.map((candidate) => <p key={candidate.procedure_id}>{candidate.canonical_name}</p>)}</div>}
    {bundle.evidence.length === 0 ? <p>Backend không trả mảnh nguồn nào.</p> :
      <div className="evidence-list">{bundle.evidence.map((item) => <details key={item.fragment_id} className="evidence">
        <summary>{item.section_type} · {item.source_id} <span>{item.fragment_id}</span></summary>
        <p>{item.text}</p><small>Vị trí nguồn: {item.source_locator}</small>
      </details>)}</div>}
  </div>
}

export default function App() {
  const [turns, setTurns] = useState<Turn[]>([])
  const [draft, setDraft] = useState('')
  const [mode, setMode] = useState<'answer' | 'retrieve'>('answer')
  const [busy, setBusy] = useState(false)
  const [health, setHealth] = useState<Health | null>(null)
  const [healthError, setHealthError] = useState(false)
  const session = useRef<string | null>(null)
  const counter = useRef(0)
  const bottom = useRef<HTMLDivElement | null>(null)

  useEffect(() => { getHealth().then(setHealth).catch(() => setHealthError(true)) }, [])
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }) }, [turns, busy])

  async function submit(event: FormEvent) {
    event.preventDefault()
    const query = draft.trim()
    if (!query || busy) return
    const id = ++counter.current
    const selectedMode = mode
    setTurns((current) => [...current, { id, query, mode: selectedMode }])
    setDraft('')
    setBusy(true)
    const body: Query = { query_text_raw: query, filters: {}, top_k: 5 }
    if (session.current) body.session_id = session.current
    try {
      const result = selectedMode === 'answer' ? await ask(body) : await retrieve(body)
      if (result.sessionId) session.current = result.sessionId
      setTurns((current) => current.map((turn) => turn.id === id ?
        selectedMode === 'answer' ? { ...turn, answer: result.data as GroundedAnswer } :
          { ...turn, bundle: result.data as EvidenceBundle } : turn))
    } catch (error) {
      setTurns((current) => current.map((turn) => turn.id === id ?
        { ...turn, error: error instanceof Error ? error.message : 'Yêu cầu chưa được xử lý.' } : turn))
    } finally { setBusy(false) }
  }

  function reset() {
    if (busy) return
    session.current = null
    setTurns([])
    setDraft('')
    setMode('answer')
  }

  function keyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit() }
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark"><SealCheck size={22} weight="fill" /></span>
        <span>Trợ lý hành chính<small>Benchmark frontend</small></span></div>
      <button className="new-chat" onClick={reset} disabled={busy}><Plus size={18} /> Phiên mới</button>
      <div className="sidebar-context"><span className="eyebrow">PHIÊN HIỆN TẠI</span>
        <p>Cuộc trao đổi được giữ trong tab này. “Phiên mới” đặt lại session gửi tới backend.</p></div>
      <div className="sidebar-footer"><span className={`health-dot ${health?.status === 'ok' ? 'online' : ''}`} />
        {health?.status === 'ok' ? 'Backend sẵn sàng' : healthError ? 'Chưa kết nối backend' : 'Đang kiểm tra backend'}</div>
    </aside>

    <main className="workspace">
      <header className="topbar"><div className="topbar-title"><span className="header-icon"><ChatCircleDots size={19} /></span>
        <div><strong>Hỏi đáp thủ tục</strong><small>Dữ liệu trả lời và trích dẫn từ backend benchmark</small></div></div>
        <span className="backend-badge"><span className={`health-dot ${health?.status === 'ok' ? 'online' : ''}`} /> Person 2 API</span></header>

      <div className="chat-scroll"><div className="chat-content">
        {!turns.length && <div className="welcome"><span className="welcome-mark"><SealCheck size={30} weight="fill" /></span>
          <span className="eyebrow">GIAO DIỆN BENCHMARK</span><h1>Bạn cần tìm hiểu<br />thủ tục nào?</h1>
          <p>Đặt câu hỏi tự nhiên. Nội dung trả lời, yêu cầu làm rõ và nguồn dẫn đều do backend cung cấp.</p>
          <div className="welcome-hint"><CheckCircle size={17} /> Mỗi phiên mới bắt đầu không có ngữ cảnh cũ</div></div>}
        {turns.map((turn) => <div className="turn" key={turn.id}>
          <div className="question"><span>{turn.query}</span></div>
          {turn.answer && <AnswerView answer={turn.answer} />}
          {turn.bundle && <RetrievalView bundle={turn.bundle} />}
          {turn.error && <div className="reply error" role="alert"><div className="reply-label"><WarningCircle size={17} /> Chưa xử lý được</div><p>{turn.error}</p></div>}
          {busy && turn.id === turns[turns.length - 1].id && !turn.answer && !turn.bundle && !turn.error &&
            <div className="reply loading"><CircleNotch size={17} className="spin" /> Đang chờ backend…</div>}
        </div>)}<div ref={bottom} />
      </div></div>

      <form className="composer-wrap" onSubmit={(event) => void submit(event)}><div className="composer">
        <textarea aria-label="Câu hỏi của bạn" value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={keyDown}
          placeholder="Nhập câu hỏi về thủ tục hành chính…" rows={2} maxLength={4000} />
        <div className="composer-bottom"><div className="mode-switch" role="group" aria-label="Chế độ yêu cầu">
          <button type="button" className={mode === 'answer' ? 'selected' : ''} onClick={() => setMode('answer')} disabled={busy}>Hỏi đáp</button>
          <button type="button" className={mode === 'retrieve' ? 'selected' : ''} onClick={() => setMode('retrieve')} disabled={busy}>Xem nguồn</button>
        </div><button className="send-button" type="submit" aria-label="Gửi câu hỏi" disabled={busy || !draft.trim()}><ArrowRight size={20} weight="bold" /></button></div>
      </div><p className="composer-note">Enter để gửi · Shift+Enter để xuống dòng · Thông tin thủ tục do backend quyết định</p></form>
    </main>
  </div>
}
