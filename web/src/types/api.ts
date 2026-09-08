export type User = { id: string; display_name: string }
export type Conversation = { id: string; title: string; created_at: string; updated_at: string }
export type Message = { id: string; conversation_id: string; role: 'user' | 'assistant'; content: string; status: 'pending' | 'completed' | 'failed'; created_at: string }
export type CreateMessageInput = { client_message_id: string; content: string }
export type CreateMessageResponse = { user_message: Message; assistant_message: Message }