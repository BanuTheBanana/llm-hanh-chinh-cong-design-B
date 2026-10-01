import type { EvidenceBundle, GroundedAnswer } from './ragClient'

export type FixtureScenario = 'answered' | 'clarification_needed' | 'insufficient_data' | 'api_error'

export const fixtureScenarios: Array<{ value: FixtureScenario; label: string }> = [
  { value: 'answered', label: 'Đã trả lời' },
  { value: 'clarification_needed', label: 'Cần làm rõ' },
  { value: 'insufficient_data', label: 'Chưa đủ dữ liệu' },
  { value: 'api_error', label: 'Lỗi API' },
]

let fixtureSessionSequence = 0

export async function runFixture(
  mode: 'answer' | 'retrieve',
  query: string,
  scenario: FixtureScenario,
  existingSessionId: string | null,
): Promise<{ data: GroundedAnswer | EvidenceBundle; sessionId: string }> {
  await new Promise((resolve) => setTimeout(resolve, 120))
  if (scenario === 'api_error') throw new Error('Lỗi API mẫu: fixture mô phỏng HTTP 503.')

  const sessionId = existingSessionId ?? `fixture-session-${++fixtureSessionSequence}`
  const createdAt = new Date().toISOString()
  const bundleId = 'fixture-bundle-001'
  const evidence = {
    fragment_id: 'fixture-fragment-001',
    procedure_id: 'fixture-procedure-001',
    text: 'DỮ LIỆU GIẢ LẬP: Thành phần hồ sơ được quy định tại mục minh họa của thủ tục.',
    score: 0.91,
    method: 'fixture',
    source_id: 'fixture-source-001',
    source_version: 'synthetic-v1',
    effective_date: null,
    source_locator: 'Mục minh họa',
    section_type: 'required_documents',
  }

  if (mode === 'retrieve') {
    return {
      data: {
        bundle_id: bundleId,
        query_text_segmented: query,
        resolved_procedure_id: evidence.procedure_id,
        confidence_status: 'resolved',
        ambiguous_candidates: [],
        evidence: [evidence],
        fusion_method: 'fixture',
        created_at: createdAt,
        top_score: evidence.score,
        second_score: 0.2,
        margin: 0.71,
      },
      sessionId,
    }
  }

  const answer: GroundedAnswer = {
    status: scenario,
    answer_text: scenario === 'answered' ? `[FIXTURE] ${evidence.text}` : '',
    clarification_prompt: scenario === 'clarification_needed'
      ? 'Đây là câu hỏi làm rõ giả lập. Bạn muốn xem thành phần hồ sơ hay thời hạn giải quyết?'
      : scenario === 'insufficient_data' ? 'Fixture không có đủ dữ liệu để trả lời yêu cầu này.' : null,
    citations: scenario === 'answered' ? [{
      claim_text: evidence.text,
      fragment_id: evidence.fragment_id,
      source_id: evidence.source_id,
      source_locator: evidence.source_locator,
    }] : [],
    evidence_bundle_id: bundleId,
    created_at: createdAt,
  }
  return { data: answer, sessionId }
}
