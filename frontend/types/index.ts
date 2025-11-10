export interface Session {
  id: string
  name: string
  title?: string
  description?: string
  status: 'active' | 'archived' | 'deleted'
  created_at: string
  updated_at: string
  archived_at?: string
  metadata: Record<string, any>
}

export interface Message {
  id: string
  session_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  metadata: Record<string, any>
}

export interface File {
  id: string
  session_id: string
  filename: string
  filepath: string
  mime_type?: string
  uploaded_at: string
  metadata: Record<string, any>
}

export interface ChatRequest {
  message: string
  session_id: string
  use_memory: boolean
}

export interface ToolExecutionDetail {
  tool_name: string
  parameters: Record<string, any>
  result: Record<string, any>
  success: boolean
  error?: string
}

export type AgentActivityStatus = 'started' | 'completed' | 'waiting' | 'error'

export interface AgentActivityEvent {
  agent_id: string
  agent_name: string
  status: AgentActivityStatus
  message?: string
  timestamp: string
}

export interface ChatResponse {
  response: string
  session_id: string
  memory_used: {
    short_term: boolean
    medium_term: string[]
    long_term: string[]
    files: string[]
  }
  tools_used: string[]
  tool_details?: ToolExecutionDetail[]
  notifications_count?: number
  high_urgency_notifications?: Array<{
    type: string
    content: any
    id: string
  }>
  agent_activity?: AgentActivityEvent[]
}

