export type User = { id: string; display_name: string }
export type Conversation = { id: string; title: string; created_at: string; updated_at: string }
export type GroundingStatus = 'ANSWER' | 'NEED_CLARIFICATION' | 'INSUFFICIENT_DATA'
export type Citation = {
  fragment_id: string
  source_id: string
  title: string
  url: string
  metadata: Record<string, unknown>
}
export type Grounding = {
  request_id: string
  evidence_bundle_id: string
  status: GroundingStatus
  corpus_version: string
  data_classification: 'D0_SYSTEM_SMOKE' | 'D1_PUBLIC_DEMO'
  prompt_version?: string | null
  provider?: string | null
  model?: string | null
  sources: Citation[]
  missing_information: string[]
}
export type Message = {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  status: 'pending' | 'completed' | 'failed'
  created_at: string
  grounding?: Grounding | null
}
export type CreateMessageInput = { client_message_id: string; content: string }
export type CreateMessageResponse = { user_message: Message; assistant_message: Message }
