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

export type Health = {
  status: string
  database?: string
  generator?: string
  active_snapshot?: string | null
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
    response = await fetch(base + path, { ...init, headers: { Accept: 'application/json', ...init?.headers } })
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
  return { data: await response.json(), sessionId: response.headers.get('X-Conversation-Session-Id') }
}

export async function getHealth(): Promise<Health> {
  const { data } = await request('/health')
  if (!object(data) || typeof data.status !== 'string') throw new Error('Health response không đúng contract.')
  return data as Health
}

async function post(path: '/api/v1/retrieve' | '/api/v1/answer', query: Query) {
  return request(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(query) })
}

export async function retrieve(query: Query) {
  const { data, sessionId } = await post('/api/v1/retrieve', query)
  return { data: bundle(data), sessionId }
}

export async function ask(query: Query) {
  const { data, sessionId } = await post('/api/v1/answer', query)
  return { data: answer(data), sessionId }
}
