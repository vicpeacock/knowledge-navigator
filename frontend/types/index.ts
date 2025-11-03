export interface Session {
  id: string
  name: string
  created_at: string
  updated_at: string
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
}

