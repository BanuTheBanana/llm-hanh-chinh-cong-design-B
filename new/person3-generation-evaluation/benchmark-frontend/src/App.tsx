import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { ArrowRight, BookOpenText, ChatCircleDots, CheckCircle, CircleNotch, MagnifyingGlass, Plus, SealCheck, SignOut, WarningCircle } from '@phosphor-icons/react'
import AccountGate from './AccountGate'
import { ask, askWithDiagnostics, getCurrentAccount, getHealth, logoutAccount, retrieve, retrieveWithDiagnostics, type Account, type Citation, type EvidenceBundle, type GroundedAnswer, type Health, type InterpretationTrace, type Query, type RetrievalDiagnostics, type StageTrace } from './api/ragClient'
import { fixtureScenarios, runFixture, type FixtureScenario } from './api/fixtureClient'

type Turn = {
  id: number
  query: string
  mode: 'answer' | 'retrieve'
  answer?: GroundedAnswer
  bundle?: EvidenceBundle
  error?: string
  fixtureScenario?: FixtureScenario
  stageTrace?: StageTrace
  traceError?: string
  retrievalDiagnostics?: RetrievalDiagnostics
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

function RetrievalView({ bundle, diagnostics }: { bundle: EvidenceBundle; diagnostics?: RetrievalDiagnostics }) {
  return <div className="reply"><div className="reply-label"><MagnifyingGlass size={17} /> Kết quả truy xuất từ backend</div>
    <p className="retrieval-note">Trạng thái: {bundle.confidence_status}. Giao diện hiển thị nguyên kết quả truy xuất; chưa diễn giải thành tư vấn thủ tục.</p>
    {diagnostics && <details className="retrieval-diagnostics" open>
      <summary>Chẩn đoán lexical retrieval <span>{diagnostics.selected_retrieval_mode}</span></summary>
      <dl className="retrieval-meta">
        <div><dt>Cấu hình truy xuất</dt><dd>{diagnostics.retrieval_mode} · đường truy vấn: {diagnostics.selected_retrieval_mode}</dd></div>
        <div><dt>Phương thức hợp nhất</dt><dd>{diagnostics.fusion_method}</dd></div>
        <div><dt>Embedding model</dt><dd>{diagnostics.embedding ? `${diagnostics.embedding.kind} · ${diagnostics.embedding.model_fingerprint}` : 'Không dùng dense model'}</dd></div>
        <div><dt>Ngưỡng cấu hình</dt><dd>{JSON.stringify(diagnostics.thresholds)}</dd></div>
        <div><dt>Bộ lọc áp dụng</dt><dd>{JSON.stringify(diagnostics.filters_applied)}</dd></div>
        <div><dt>Trường yêu cầu</dt><dd>{diagnostics.requested_section_types.join(', ') || 'Chưa nhận diện'}</dd></div>
        <div><dt>Thủ tục đã chọn</dt><dd>{diagnostics.selected_procedure_id ?? 'Chưa phân giải'}</dd></div>
        <div><dt>Điểm {diagnostics.score_type}</dt><dd>Top: {diagnostics.top_score?.toFixed(3) ?? 'không có'} · Hạng nhì: {diagnostics.second_score?.toFixed(3) ?? 'không có'} · Margin: {diagnostics.margin?.toFixed(3) ?? 'không có'}</dd></div>
        <div><dt>Đoạn đủ điều kiện</dt><dd>{diagnostics.eligible_fragment_count}</dd></div>
      </dl>
      {diagnostics.exact_matches.length > 0 && <div className="exact-match-list"><strong>Khớp tên/mã chính thức</strong>
        {diagnostics.exact_matches.map((match, index) => <p key={`${match.procedure_id}-${index}`}>{match.matched_term} · {match.canonical_name} · {match.procedure_id}</p>)}</div>}
      {diagnostics.ranked_candidates.length === 0 ? <p>Không có ứng viên phù hợp.</p> :
        <div className="rank-table-wrap"><table className="rank-table"><thead><tr><th>Hạng</th><th>Thủ tục</th><th>ID</th><th>{diagnostics.score_type}</th><th>Trường / đoạn</th></tr></thead>
          <tbody>{diagnostics.ranked_candidates.map((candidate) => <tr key={candidate.procedure_id}>
            <td>{candidate.rank}</td><td>{candidate.canonical_name}{candidate.exact_match ? ' · exact' : ''}</td><td>{candidate.procedure_id}</td>
            <td>{candidate.score.toFixed(3)}</td><td>{candidate.field_types.join(', ') || '—'}<small>{candidate.fragment_ids.join(', ') || '—'}</small></td>
          </tr>)}</tbody></table></div>}
    </details>}
    {bundle.ambiguous_candidates?.length > 0 && <div className="candidate-list"><strong>Các ứng viên backend trả về</strong>
      {bundle.ambiguous_candidates.map((candidate) => <p key={candidate.procedure_id}>{candidate.canonical_name}</p>)}</div>}
    {bundle.evidence.length === 0 ? <p>Backend không trả mảnh nguồn nào.</p> :
      <div className="evidence-list">{bundle.evidence.map((item) => <details key={item.fragment_id} className="evidence">
        <summary>{item.section_type} · {item.source_id} <span>{item.fragment_id}</span></summary>
        <p>{item.text}</p><small>Vị trí nguồn: {item.source_locator}</small>
      </details>)}</div>}
  </div>
}

function TraceView({ trace }: { trace: InterpretationTrace }) {
  return <details className="trace-panel"><summary>Diễn giải trước truy xuất <span>{trace.segmenter.backend} · {trace.segmenter.config_fingerprint}</span></summary>
    <dl className="trace-grid">
      <div><dt>Câu hỏi gốc</dt><dd>{trace.query_text_raw}</dd></div>
      <div><dt>Chuẩn hóa</dt><dd>{trace.normalized_query_text}</dd></div>
      <div><dt>Đã phân đoạn</dt><dd>{trace.segmented_query_text}</dd></div>
      <div><dt>Bộ lọc nhận diện</dt><dd>{JSON.stringify(trace.explicit_filters)}</dd></div>
      <div><dt>Bộ lọc áp dụng</dt><dd>{JSON.stringify(trace.resolved_filters)}</dd></div>
      <div><dt>Trường được yêu cầu</dt><dd>{trace.requested_section_types.join(', ') || 'Chưa nhận diện'}</dd></div>
      <div><dt>Hội thoại trước</dt><dd>{trace.prior_state.exists ? JSON.stringify(trace.prior_state) : 'Chưa có trạng thái trước'}</dd></div>
      <div><dt>Kết quả diễn giải</dt><dd>{trace.interpretation_outcome} · RetrievalInput {trace.retrieval_input_valid ? 'hợp lệ' : 'không hợp lệ'}</dd></div>
    </dl>
  </details>
}

function StageTraceView({ trace }: { trace: StageTrace }) {
  const sufficiency = trace.grounding.sufficiency
  const citations = trace.grounding.citation_binding
  const conversation = trace.conversation
  return <div className="stage-trace">
    <TraceView trace={trace.interpretation} />
    <details className="pipeline-panel" open>
      <summary>Evidence, grounding và trạng thái <span>{trace.trace_id}</span></summary>
      <div className="pipeline-grid">
        <div><dt>Retrieval</dt><dd>{trace.retrieval.selected_retrieval_mode} · {trace.retrieval.confidence_status} · {trace.retrieval.ranked_candidates.length} ứng viên</dd></div>
        <div><dt>Điểm đầu / hạng nhì</dt><dd>{trace.retrieval.top_score?.toFixed(3) ?? 'không có'} / {trace.retrieval.second_score?.toFixed(3) ?? 'không có'} · margin {trace.retrieval.margin?.toFixed(3) ?? 'không có'}</dd></div>
        <div><dt>Đủ bằng chứng</dt><dd className={`stage-status ${sufficiency.status}`}>{sufficiency.status} · có: {sufficiency.available_section_types.join(', ') || 'không có'} · thiếu: {sufficiency.missing_section_types.join(', ') || 'không có'}</dd></div>
        <div><dt>Kiểm tra trích dẫn</dt><dd className={`stage-status ${citations.status}`}>{citations.status} · {citations.checked_count} trích dẫn</dd></div>
        <div><dt>Generator</dt><dd>{trace.grounding.generation.mode} · {trace.grounding.generation.status}</dd></div>
        <div><dt>Filter được mang theo</dt><dd>{JSON.stringify(conversation.carried_filters)}</dd></div>
        <div><dt>Chuyển trạng thái</dt><dd>{conversation.state_reset_or_replacement_reason}</dd></div>
        <div><dt>Thủ tục trước / hiện tại</dt><dd>{conversation.previous_state?.last_resolved_procedure_id ?? 'không có'} / {conversation.current_state.last_resolved_procedure_id ?? 'không phân giải'}</dd></div>
      </div>
      {sufficiency.problems.length > 0 && <div className="stage-problems"><strong>Lý do chưa đủ</strong>{sufficiency.problems.map((problem, index) => <p key={`${problem}-${index}`}>{problem}</p>)}</div>}
      {citations.problems.length > 0 && <div className="stage-problems"><strong>Lỗi gắn trích dẫn</strong>{citations.problems.map((problem, index) => <p key={`${problem}-${index}`}>{problem}</p>)}</div>}
      <div className="stage-evidence"><strong>Mảnh bằng chứng ({trace.evidence.length})</strong>
        {trace.evidence.length === 0 ? <p>Không có mảnh bằng chứng.</p> : trace.evidence.map((item) => <details className="stage-evidence-item" key={item.fragment_id}>
          <summary>{item.section_type} · {item.fragment_id} · {item.source_id}</summary>
          <p>{item.text}</p><small>Thủ tục: {item.procedure_id} · Phiên bản nguồn: {item.source_version} · Ngày hiệu lực: {item.effective_date ?? 'chưa khai báo'}</small>
          <small>Vị trí nguồn: {item.source_locator} · Phương thức: {item.method} · Điểm: {item.score.toFixed(3)}</small>
        </details>)}
      </div>
    </details>
  </div>
}

export default function App() {
  const [turns, setTurns] = useState<Turn[]>([])
  const [draft, setDraft] = useState('')
  const [mode, setMode] = useState<'answer' | 'retrieve'>('answer')
  const [requestSource, setRequestSource] = useState<'live' | 'fixture'>('live')
  const [fixtureScenario, setFixtureScenario] = useState<FixtureScenario>('answered')
  const [account, setAccount] = useState<Account | null>(null)
  const [accountLoading, setAccountLoading] = useState(true)
  const [accountNotice, setAccountNotice] = useState('')
  const [fixtureSandbox, setFixtureSandbox] = useState(false)
  const [fixtureAccount, setFixtureAccount] = useState('fixture-a')
  const [traceEnabled, setTraceEnabled] = useState(false)
  const [busy, setBusy] = useState(false)
  const [health, setHealth] = useState<Health | null>(null)
  const [healthError, setHealthError] = useState(false)
  const liveSession = useRef<string | null>(null)
  const fixtureSession = useRef<string | null>(null)
  const counter = useRef(0)
  const bottom = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealthError(true))
    getCurrentAccount().then(setAccount).catch(() => undefined).finally(() => setAccountLoading(false))
  }, [])
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }) }, [turns, busy])

  async function submit(event: FormEvent) {
    event.preventDefault()
    const query = draft.trim()
    if (!query || busy || (!account && !fixtureSandbox) || (!account && requestSource !== 'fixture')) return
    const id = ++counter.current
    const selectedMode = mode
    const selectedSource = requestSource
    const selectedScenario = fixtureScenario
    const selectedTrace = traceEnabled
    setTurns((current) => [...current, {
      id, query, mode: selectedMode,
      fixtureScenario: selectedSource === 'fixture' ? selectedScenario : undefined,
    }])
    setDraft('')
    setBusy(true)
    const body: Query = { query_text_raw: query, filters: {}, top_k: 5 }
    try {
      if (selectedSource === 'fixture') {
        const result = await runFixture(selectedMode, query, selectedScenario, fixtureSession.current)
        fixtureSession.current = result.sessionId
        setTurns((current) => current.map((turn) => turn.id === id ?
          selectedMode === 'answer' ? { ...turn, answer: result.data as GroundedAnswer } :
            { ...turn, bundle: result.data as EvidenceBundle } : turn))
      } else {
        if (liveSession.current) body.session_id = liveSession.current
        if (selectedTrace && selectedMode === 'answer') {
          const result = await askWithDiagnostics(body)
          if (result.sessionId) liveSession.current = result.sessionId
          setTurns((current) => current.map((turn) => turn.id === id ?
            { ...turn, answer: result.data, stageTrace: result.stageTrace } : turn))
        } else if (selectedMode === 'answer') {
          const result = await ask(body)
          if (result.sessionId) liveSession.current = result.sessionId
          setTurns((current) => current.map((turn) => turn.id === id ? { ...turn, answer: result.data } : turn))
        } else if (selectedTrace) {
          const result = await retrieveWithDiagnostics(body)
          if (result.sessionId) liveSession.current = result.sessionId
          setTurns((current) => current.map((turn) => turn.id === id ?
            { ...turn, bundle: result.data, retrievalDiagnostics: result.diagnostics, stageTrace: result.stageTrace } : turn))
        } else {
          const result = await retrieve(body)
          if (result.sessionId) liveSession.current = result.sessionId
          setTurns((current) => current.map((turn) => turn.id === id ? { ...turn, bundle: result.data } : turn))
        }
      }
    } catch (error) {
      setTurns((current) => current.map((turn) => turn.id === id ?
        { ...turn, error: error instanceof Error ? error.message : 'Yêu cầu chưa được xử lý.' } : turn))
    } finally { setBusy(false) }
  }

  function reset() {
    if (busy) return
    liveSession.current = null
    fixtureSession.current = null
    setTurns([])
    setDraft('')
    setMode('answer')
  }

  function enterFixtureSandbox() {
    setFixtureSandbox(true)
    setFixtureAccount('fixture-a')
    setRequestSource('fixture')
    fixtureSession.current = null
  }

  function authenticate(account: Account) {
    liveSession.current = null
    fixtureSession.current = null
    setTurns([])
    setAccount(account)
    setAccountNotice('')
    setFixtureSandbox(false)
    setRequestSource('live')
  }

  async function signOut() {
    if (busy) return
    setBusy(true)
    try { await logoutAccount(); setAccountNotice('') }
    catch { setAccountNotice('Không thể xác nhận đăng xuất với máy chủ. Đóng phiên trình duyệt dùng chung sau khi rời khỏi.') }
    finally {
      setAccount(null)
      setTurns([])
      liveSession.current = null
      fixtureSession.current = null
      setBusy(false)
    }
  }

  function keyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit() }
  }

  if (accountLoading) return <main className="account-gate"><p>Đang kiểm tra phiên đăng nhập…</p></main>
  if (!account && !fixtureSandbox) return <AccountGate onAuthenticated={authenticate} onFixture={enterFixtureSandbox} notice={accountNotice} />

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark"><SealCheck size={22} weight="fill" /></span>
        <span>Trợ lý hành chính<small>Benchmark frontend</small></span></div>
      <button className="new-chat" onClick={reset} disabled={busy}><Plus size={18} /> Phiên mới</button>
      <div className="account-block"><div><span className="eyebrow">TÀI KHOẢN</span><strong>{fixtureSandbox ? `Fixture · ${fixtureAccount}` : account?.username}</strong></div>
        {account && <button className="logout-button" type="button" title="Đăng xuất" aria-label="Đăng xuất" onClick={() => void signOut()} disabled={busy}><SignOut size={18} /></button>}
        {fixtureSandbox && <button className="logout-button" type="button" onClick={() => { setFixtureSandbox(false); setTurns([]); fixtureSession.current = null }}>Thoát fixture</button>}
      </div>
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
        {import.meta.env.DEV && <div className="dev-tools" aria-label="Công cụ kiểm thử giao diện">
          <label>Nguồn yêu cầu<select value={requestSource} onChange={(event) => setRequestSource(event.target.value as 'live' | 'fixture')}>
            <option value="live" disabled={fixtureSandbox}>Person 2 API</option><option value="fixture">Fixture local</option>
          </select></label>
          {requestSource === 'fixture' && <>
            <label>Trạng thái mẫu<select value={fixtureScenario} onChange={(event) => setFixtureScenario(event.target.value as FixtureScenario)}>
              {fixtureScenarios.map((scenario) => <option value={scenario.value} key={scenario.value}>{scenario.label}</option>)}
            </select></label>
            <span className="fixture-session">Session: <code>{fixtureSession.current ?? 'chưa tạo'}</code></span>
            {fixtureSandbox && <label>Tài khoản giả lập<select value={fixtureAccount} onChange={(event) => { setFixtureAccount(event.target.value); fixtureSession.current = null; setTurns([]) }}>
              <option value="fixture-a">Tài khoản A</option><option value="fixture-b">Tài khoản B</option>
            </select></label>}
            <strong>{fixtureSandbox ? 'Tài khoản giả lập, chỉ trong trình duyệt' : 'Chỉ dữ liệu thử nghiệm, không gọi backend'}</strong>
          </>}
          {account && <label className="trace-toggle"><input type="checkbox" checked={traceEnabled} onChange={(event) => setTraceEnabled(event.target.checked)} /> Trace phát triển V2–V4</label>}
        </div>}
        {!turns.length && <div className="welcome"><span className="welcome-mark"><SealCheck size={30} weight="fill" /></span>
          <span className="eyebrow">GIAO DIỆN BENCHMARK</span><h1>Bạn cần tìm hiểu<br />thủ tục nào?</h1>
          <p>Đặt câu hỏi tự nhiên. Nội dung trả lời, yêu cầu làm rõ và nguồn dẫn đều do backend cung cấp.</p>
          <div className="welcome-hint"><CheckCircle size={17} /> Mỗi phiên mới bắt đầu không có ngữ cảnh cũ</div></div>}
        {turns.map((turn) => <div className="turn" key={turn.id}>
          <div className="question"><span>{turn.query}</span></div>
          {turn.fixtureScenario && <div className="fixture-mark">FIXTURE · {turn.fixtureScenario}</div>}
          {turn.stageTrace && <StageTraceView trace={turn.stageTrace} />}
          {turn.traceError && <div className="trace-error">Trace không khả dụng: {turn.traceError}</div>}
          {turn.answer && <AnswerView answer={turn.answer} />}
          {turn.bundle && <RetrievalView bundle={turn.bundle} diagnostics={turn.retrievalDiagnostics} />}
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
