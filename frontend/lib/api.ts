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

// Request interceptor: Add JWT token and multi-tenant headers
api.interceptors.request.use((config) => {
  // Add JWT token if available (priority 1: authentication)
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
  }
  
  // Add X-API-Key header if available (for API key auth, fallback)
  const apiKey = typeof window !== 'undefined' 
    ? localStorage.getItem('api_key') || process.env.NEXT_PUBLIC_API_KEY
    : process.env.NEXT_PUBLIC_API_KEY
  
  if (apiKey) {
    config.headers['X-API-Key'] = apiKey
  }
  
  // Add X-Tenant-ID header if available (for development/testing)
  const tenantId = typeof window !== 'undefined'
    ? localStorage.getItem('tenant_id') || process.env.NEXT_PUBLIC_TENANT_ID
    : process.env.NEXT_PUBLIC_TENANT_ID
  
  if (tenantId) {
    config.headers['X-Tenant-ID'] = tenantId
  }
  
  return config
})

// Response interceptor: Handle 401 (token expired) with automatic refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // If 401 and not already retrying
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      try {
        // Try to refresh token
        const refreshToken = typeof window !== 'undefined' 
          ? localStorage.getItem('refresh_token')
          : null

        if (refreshToken) {
          const response = await api.post('/api/v1/auth/refresh', {
            refresh_token: refreshToken
          })

          const { access_token } = response.data
          
          // Update token in localStorage
          if (typeof window !== 'undefined') {
            localStorage.setItem('access_token', access_token)
          }

          // Update authorization header and retry original request
          originalRequest.headers['Authorization'] = `Bearer ${access_token}`
          return api(originalRequest)
        }
      } catch (refreshError) {
        // Refresh failed, clear tokens and redirect to login
        if (typeof window !== 'undefined') {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          // Redirect will be handled by middleware or component
        }
        return Promise.reject(refreshError)
      }
    }

    return Promise.reject(error)
  }
)

// Auth API
export const authApi = {
  login: (data: { email: string; password: string }) =>
    api.post('/api/v1/auth/login', data),
  register: (data: { email: string; password: string; name?: string; tenant_id?: string }) =>
    api.post('/api/v1/auth/register', data),
  logout: () => api.post('/api/v1/auth/logout'),
  refresh: (data: { refresh_token: string }) =>
    api.post('/api/v1/auth/refresh', data),
  me: () => api.get('/api/v1/auth/me'),
  changePassword: (data: { current_password: string; new_password: string }) =>
    api.post('/api/v1/auth/change-password', data),
  verifyEmail: (token: string) =>
    api.get('/api/v1/auth/verify-email', { params: { token } }),
  requestPasswordReset: (data: { email: string }) =>
    api.post('/api/v1/auth/password-reset/request', data),
  confirmPasswordReset: (data: { token: string; new_password: string }) =>
    api.post('/api/v1/auth/password-reset/confirm', data),
}

// Users API (admin only)
export const usersApi = {
  list: (filters?: { role?: string; active?: boolean }) =>
    api.get('/api/v1/users', { params: filters }),
  create: (data: { email: string; name?: string; password?: string; role?: string; send_invitation_email?: boolean }) =>
    api.post('/api/v1/users', data),
  get: (id: string) => api.get(`/api/v1/users/${id}`),
  update: (id: string, data: { name?: string; role?: string; active?: boolean }) =>
    api.put(`/api/v1/users/${id}`, data),
  delete: (id: string) => api.delete(`/api/v1/users/${id}`),
}

// API Keys API
export const apikeysApi = {
  create: (data: { name?: string; expires_in_days?: number }) =>
    api.post('/api/v1/apikeys', data),
  list: (activeOnly: boolean = false) =>
    api.get('/api/v1/apikeys', { params: { active_only: activeOnly } }),
  revoke: (keyId: string) =>
    api.delete(`/api/v1/apikeys/${keyId}`),
}

// Sessions API
export const sessionsApi = {
  list: (status?: string) => api.get('/api/sessions/', { params: status ? { status } : {} }),
  get: (id: string) => api.get(`/api/sessions/${id}`),
  create: (data: { name: string; title?: string; description?: string; metadata?: Record<string, any> }) =>
    api.post('/api/sessions/', data),
  update: (id: string, data: { name?: string; title?: string; description?: string; status?: string; metadata?: Record<string, any> }) =>
    api.put(`/api/sessions/${id}`, data),
  delete: (id: string) => api.delete(`/api/sessions/${id}`),
  archive: (id: string) => api.post(`/api/sessions/${id}/archive`),
  restore: (id: string) => api.post(`/api/sessions/${id}/restore`),
  getMessages: (id: string) => api.get(`/api/sessions/${id}/messages`),
  chat: (id: string, message: string, useMemory: boolean = true, forceWebSearch: boolean = false) =>
    api.post(`/api/sessions/${id}/chat`, { message, session_id: id, use_memory: useMemory, force_web_search: forceWebSearch }, { timeout: 300000 }), // 5 minutes to allow long-running background tasks
  getMemory: (id: string) => api.get(`/api/sessions/${id}/memory`),
  cleanContradictionNotifications: () => api.delete('/api/sessions/notifications/contradictions'),
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
      mcp: {
    connect: (serverUrl: string, name?: string) =>
      api.post('/api/integrations/mcp/connect', { server_url: serverUrl, name: name || 'MCP Server' }),
    listIntegrations: () => api.get('/api/integrations/mcp/integrations'),
    getTools: (integrationId: string) => api.get(`/api/integrations/mcp/${integrationId}/tools`, { timeout: 45000 }), // 45 seconds timeout
    selectTools: (integrationId: string, toolNames: string[]) =>
      api.post(`/api/integrations/mcp/${integrationId}/tools/select`, { tool_names: toolNames }),
    deleteIntegration: (integrationId: string) =>
      api.delete(`/api/integrations/mcp/integrations/${integrationId}`),
    test: (integrationId: string) => api.post(`/api/integrations/mcp/${integrationId}/test`, { timeout: 45000 }),
    debug: (integrationId: string) => api.get(`/api/integrations/mcp/${integrationId}/debug`),
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

