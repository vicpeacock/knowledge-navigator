import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: false,
  timeout: 120000, // 2 minutes - increased for longer responses (file summaries can take time)
})

// Sessions API
export const sessionsApi = {
  list: () => api.get('/api/sessions/'),
  get: (id: string) => api.get(`/api/sessions/${id}`),
  create: (data: { name: string; metadata?: Record<string, any> }) =>
    api.post('/api/sessions/', data),
  update: (id: string, data: { name?: string; metadata?: Record<string, any> }) =>
    api.put(`/api/sessions/${id}`, data),
  delete: (id: string) => api.delete(`/api/sessions/${id}`),
  getMessages: (id: string) => api.get(`/api/sessions/${id}/messages`),
  chat: (id: string, message: string, useMemory: boolean = true) =>
    api.post(`/api/sessions/${id}/chat`, { message, session_id: id, use_memory: useMemory }),
  getMemory: (id: string) => api.get(`/api/sessions/${id}/memory`),
}

// Files API
export const filesApi = {
  upload: (sessionId: string, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post(`/api/files/upload/${sessionId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  list: (sessionId: string) => api.get(`/api/files/session/${sessionId}`),
  get: (fileId: string) => api.get(`/api/files/id/${fileId}`),
  delete: (fileId: string) => api.delete(`/api/files/id/${fileId}`),
  search: (sessionId: string, query: string, nResults: number = 5) =>
    api.post(`/api/files/${sessionId}/search`, { query, n_results: nResults }),
}

// Memory API
export const memoryApi = {
  getMediumTerm: (sessionId: string, query: string, nResults: number = 5) =>
    api.get(`/api/memory/medium/${sessionId}`, { params: { query, n_results: nResults } }),
  getLongTerm: (query: string, nResults: number = 5, minImportance?: number) =>
    api.get('/api/memory/long', { params: { query, n_results: nResults, min_importance: minImportance } }),
  addLongTerm: (content: string, learnedFromSessions: string[], importanceScore: number = 0.5) =>
    api.post('/api/memory/long', {
      content,
      learned_from_sessions: learnedFromSessions,
      importance_score: importanceScore,
    }),
}

// Tools API
export const toolsApi = {
  list: () => api.get('/api/tools/list'),
  call: (toolName: string, parameters: Record<string, any>) =>
    api.post('/api/tools/call', { tool_name: toolName, parameters }),
  browserNavigate: (url: string) => api.get('/api/tools/browser/navigate', { params: { url } }),
  browserSearch: (query: string) => api.get('/api/tools/browser/search', { params: { query } }),
}

// Web API
export const webApi = {
  search: (query: string, maxResults?: number) =>
    api.post('/api/web/search', { query, max_results: maxResults }),
  navigate: (url: string) => api.post('/api/web/navigate', { url }),
}

// Integrations API
export const integrationsApi = {
      calendar: {
        authorize: (integrationId?: string) => {
          const params = integrationId ? { integration_id: integrationId } : {}
          return api.get('/api/integrations/calendars/oauth/authorize', { params })
        },
        getEvents: (provider: string = 'google', startTime?: string, endTime?: string, integrationId?: string) => {
          const params: any = { provider }
          if (startTime) params.start_time = startTime
          if (endTime) params.end_time = endTime
          if (integrationId) params.integration_id = integrationId
          return api.get('/api/integrations/calendars/events', { params })
        },
        query: (query: string, provider: string = 'google', integrationId?: string) =>
          api.post('/api/integrations/calendars/query', {
            query,
            provider,
            integration_id: integrationId,
          }),
        listIntegrations: (provider?: string) => {
          const params = provider ? { provider } : {}
          return api.get('/api/integrations/calendars/integrations', { params })
        },
        deleteIntegration: (integrationId: string) =>
          api.delete(`/api/integrations/calendars/integrations/${integrationId}`),
      },
      email: {
        authorize: (integrationId?: string) => {
          const params = integrationId ? { integration_id: integrationId } : {}
          return api.get('/api/integrations/emails/oauth/authorize', { params })
        },
        getMessages: (provider: string = 'gmail', maxResults: number = 10, query?: string, integrationId?: string, includeBody?: boolean) => {
          const params: any = { provider, max_results: maxResults }
          if (query) params.query = query
          if (integrationId) params.integration_id = integrationId
          if (includeBody) params.include_body = includeBody
          return api.get('/api/integrations/emails/messages', { params })
        },
        summarize: (integrationId: string, maxEmails: number = 5) =>
          api.post(`/api/integrations/emails/summarize?integration_id=${integrationId}&max_emails=${maxEmails}`),
        listIntegrations: (provider?: string) => {
          const params = provider ? { provider } : {}
          return api.get('/api/integrations/emails/integrations', { params })
        },
        deleteIntegration: (integrationId: string) =>
          api.delete(`/api/integrations/emails/integrations/${integrationId}`),
      },
}

export default api

