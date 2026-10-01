/** Browser-only HTTP boundary for Person 2. No legacy API/client imports. */
export type Filters = {
  jurisdiction?: string | null
  effective_date?: string | null
  scope?: string | null
}

export type Query = {
  query_text_raw: string
  session_id?: string
  filters: Filters
  top_k: number
}

export type Citation = {
  claim_text: string
  fragment_id: string
  source_id: string
  source_locator: string
}

export type GroundedAnswer = {
  status: 'answered' | 'clarification_needed' | 'insufficient_data'
  answer_text: string
  clarification_prompt?: string | null
  citations: Citation[]
  evidence_bundle_id: string
  created_at: string
}

export type Evidence = {
  fragment_id: string
  procedure_id: string
  text: string
  score: number
  method: string
  source_id: string
  source_version: string
  effective_date: string | null
  source_locator: string
  section_type: string
}

export type EvidenceBundle = {
  bundle_id: string
  query_text_segmented: string
  resolved_procedure_id: string | null
  confidence_status: 'resolved' | 'ambiguous' | 'low_confidence'
  ambiguous_candidates: Array<{ procedure_id: string; canonical_name: string; score: number }>
  evidence: Evidence[]
  fusion_method: string
  created_at: string
  top_score?: number | null
  second_score?: number | null
  margin?: number | null
}

export type RankedCandidate = {
  rank: number
  procedure_id: string
  canonical_name: string
  score: number
  exact_match: boolean
  field_types: string[]
  fragment_ids: string[]
}

export type RetrievalDiagnostics = {
  selected_retrieval_mode: string
  retrieval_mode: string
  fusion_method: string
  score_type: string
  filters_applied: Filters
  requested_section_types: string[]
  exact_matches: Array<{ procedure_id: string; canonical_name: string; matched_term: string }>
  selected_procedure_id: string | null
  ranked_candidates: RankedCandidate[]
  top_score: number | null
  second_score: number | null
  margin: number | null
  confidence_status: 'resolved' | 'ambiguous' | 'low_confidence'
  eligible_fragment_count: number
  embedding: { kind: string; model_fingerprint: string; query_prefix: string; document_prefix: string; device: string; batch_size: number } | null
  thresholds: { score_floor: number; margin_floor: number; dense_min_similarity: number | null; rrf_k: number | null }
}

export type Health = {
  status: string
  database?: string
  generator?: string
  active_snapshot?: string | null
}

export type Account = { account_id: string; username: string }

export type InterpretationTrace = {
  trace_id: string
  query_text_raw: string
  normalized_query_text: string
  segmented_query_text: string
  explicit_filters: Filters
  resolved_filters: Filters
  requested_section_types: string[]
  follow_up: boolean
  prior_state: {
    exists: boolean
    active_filters: Filters
    last_resolved_procedure_id: string | null
    last_requested_section_types: string[]
    unresolved_references: string[]
  }
  segmenter: { backend: string; backend_version: string; config_fingerprint: string }
  interpretation_outcome: string
  retrieval_input_valid: boolean
}

export type GroundingDiagnostics = {
  sufficiency: {
    status: 'passed' | 'failed'
    requested_section_types: string[]
    available_section_types: string[]
    missing_section_types: string[]
    problems: string[]
  }
  citation_binding: { status: string; checked_count: number; problems: string[] }
  generation: { mode: string; status: string }
}

export type ConversationTrace = {
  follow_up: boolean
  previous_state: {
    active_filters: Filters
    last_resolved_procedure_id: string | null
    last_requested_section_types: string[]
    unresolved_references: string[]
  } | null
  current_state: {
    active_filters: Filters
    last_resolved_procedure_id: string | null
    last_requested_section_types: string[]
    unresolved_references: string[]
  }
  carried_filters: Filters
  state_reset_or_replacement_reason: string
}

export type StageTrace = {
  trace_id: string
  interpretation: InterpretationTrace
  retrieval: RetrievalDiagnostics
  evidence: Evidence[]
  grounding: GroundingDiagnostics
  conversation: ConversationTrace
}

// Vite proxies these paths during development because Person 2 currently has no
// CORS middleware. A static build calls the configured backend origin directly.
const configuredBase = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')
const base = import.meta.env.DEV ? '' : configuredBase

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function answer(value: unknown): GroundedAnswer {
  if (!object(value) || !['answered', 'clarification_needed', 'insufficient_data'].includes(String(value.status)) ||
      typeof value.answer_text !== 'string' || !Array.isArray(value.citations) ||
      typeof value.evidence_bundle_id !== 'string' || typeof value.created_at !== 'string') {
    throw new Error('Backend trả về GroundedAnswer không đúng contract.')
  }
  if (value.status === 'clarification_needed' && typeof value.clarification_prompt !== 'string') {
    throw new Error('Backend thiếu câu hỏi làm rõ.')
  }
  return value as GroundedAnswer
}

function bundle(value: unknown): EvidenceBundle {
  if (!object(value) || typeof value.bundle_id !== 'string' || !Array.isArray(value.evidence) ||
      !['resolved', 'ambiguous', 'low_confidence'].includes(String(value.confidence_status))) {
    throw new Error('Backend trả về EvidenceBundle không đúng contract.')
  }
  return value as EvidenceBundle
}

async function request(path: string, init?: RequestInit): Promise<{ data: unknown; sessionId: string | null }> {
  let response: Response
  try {
    response = await fetch(base + path, { ...init, credentials: 'include', headers: { Accept: 'application/json', ...init?.headers } })
  } catch {
    throw new Error('Không kết nối được backend. Kiểm tra VITE_API_BASE_URL và trạng thái dịch vụ.')
  }
  if (!response.ok) {
    let detail = ''
    try {
      const body: unknown = await response.json()
      if (object(body) && typeof body.detail === 'string') detail = body.detail
    } catch { /* HTTP error without JSON body */ }
    throw new Error(detail || `Backend trả HTTP ${response.status}.`)
  }
  return { data: response.status === 204 ? null : await response.json(), sessionId: response.headers.get('X-Conversation-Session-Id') }
}

export async function getHealth(): Promise<Health> {
  const { data } = await request('/health')
  if (!object(data) || typeof data.status !== 'string') throw new Error('Health response không đúng contract.')
  return data as Health
}

async function post(path: '/api/v1/retrieve' | '/api/v1/answer' | '/api/v1/interpret' | '/api/v1/retrieve/trace' | '/api/v1/answer/trace', query: Query) {
  return request(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(query) })
}

function parseAccount(value: unknown): Account {
  if (!object(value) || typeof value.account_id !== 'string' || typeof value.username !== 'string') {
    throw new Error('Backend trả về tài khoản không đúng contract.')
  }
  return value as Account
}

async function authenticate(path: '/api/v1/auth/register' | '/api/v1/auth/login', username: string, password: string) {
  const { data } = await request(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }) })
  return parseAccount(data)
}

export const registerAccount = (username: string, password: string) => authenticate('/api/v1/auth/register', username, password)
export const loginAccount = (username: string, password: string) => authenticate('/api/v1/auth/login', username, password)
export async function getCurrentAccount() {
  const { data } = await request('/api/v1/auth/me')
  return parseAccount(data)
}
export async function logoutAccount() {
  await request('/api/v1/auth/logout', { method: 'POST' })
}

export async function retrieve(query: Query) {
  const { data, sessionId } = await post('/api/v1/retrieve', query)
  return { data: bundle(data), sessionId }
}

export async function retrieveWithDiagnostics(query: Query) {
  const { data, sessionId } = await post('/api/v1/retrieve/trace', query)
  if (!object(data) || !object(data.evidence_bundle) || !object(data.diagnostics) ||
      typeof data.diagnostics.selected_retrieval_mode !== 'string' || !Array.isArray(data.diagnostics.ranked_candidates)) {
    throw new Error('Backend trả về trace truy xuất không đúng contract.')
  }
  return {
    data: bundle(data.evidence_bundle),
    diagnostics: data.diagnostics as RetrievalDiagnostics,
    stageTrace: data.stage_trace as StageTrace,
    sessionId,
  }
}

export async function ask(query: Query) {
  const { data, sessionId } = await post('/api/v1/answer', query)
  return { data: answer(data), sessionId }
}

export async function askWithDiagnostics(query: Query) {
  const { data, sessionId } = await post('/api/v1/answer/trace', query)
  if (!object(data) || !object(data.grounded_answer) || !object(data.stage_trace) ||
      typeof data.stage_trace.trace_id !== 'string' || !object(data.stage_trace.grounding) ||
      !object(data.stage_trace.conversation)) {
    throw new Error('Backend trả về trace grounding không đúng contract.')
  }
  return {
    data: answer(data.grounded_answer),
    stageTrace: data.stage_trace as StageTrace,
    sessionId,
  }
}

export async function interpret(query: Query) {
  const { data, sessionId } = await post('/api/v1/interpret', query)
  if (!object(data) || typeof data.trace_id !== 'string' || typeof data.segmented_query_text !== 'string' ||
      typeof data.retrieval_input_valid !== 'boolean') {
    throw new Error('Backend trả về trace diễn giải không đúng contract.')
  }
  return { data: data as InterpretationTrace, sessionId }
}
