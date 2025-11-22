import axios from 'axios'
import { getCurrentTraceId, trackApiRequest, trackApiResponse } from './tracing'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: false,
  timeout: 300000, // 5 minutes - increased for long-running operations (Gmail API, LangGraph, tool execution)
})

// Request interceptor: Add JWT token, multi-tenant headers, and trace ID
api.interceptors.request.use((config) => {
  // Preserve existing metadata if present (for retries)
  const existingMetadata = (config as any).metadata
  
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
  
  // Add trace ID for observability (only if not already set)
  if (!existingMetadata) {
    try {
      const traceId = getCurrentTraceId()
      if (traceId) {
        config.headers['X-Trace-ID'] = traceId
        
        // Store metadata for response tracking
        const startTime = Date.now()
        ;(config as any).metadata = { startTime, traceId }
        
        // Track request
        trackApiRequest(config.method?.toUpperCase() || 'GET', config.url || '', traceId, startTime)
      }
    } catch (error) {
      // If tracing fails, continue without it (don't break the request)
      console.warn('Failed to add trace ID to request:', error)
    }
  } else {
    // Preserve existing metadata and trace ID
    if (existingMetadata.traceId) {
      config.headers['X-Trace-ID'] = existingMetadata.traceId
    }
  }
  
  return config
})

// Response interceptor: Track responses and handle 401 (token expired) with automatic refresh
api.interceptors.response.use(
  (response) => {
    // Track successful response (only if config exists)
    if (response.config) {
      const metadata = (response.config as any).metadata
      if (metadata) {
        const duration = Date.now() - metadata.startTime
        trackApiResponse(
          response.config.method?.toUpperCase() || 'GET',
          response.config.url || '',
          metadata.traceId,
          response.status,
          duration
        )
        
        // Store backend trace ID if present
        const backendTraceId = response.headers['x-trace-id']
        if (backendTraceId && process.env.NODE_ENV === 'development') {
          console.log(`[Trace: ${metadata.traceId}] Backend Trace ID: ${backendTraceId}`)
        }
      }
    }
    return response
  },
  async (error) => {
    const originalRequest = error.config
    
    // Track error response
    const metadata = originalRequest?.metadata
    if (metadata) {
      const duration = Date.now() - metadata.startTime
      trackApiResponse(
        originalRequest?.method?.toUpperCase() || 'GET',
        originalRequest?.url || '',
        metadata.traceId,
        error.response?.status || 0,
        duration,
        error
      )
    }

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
          
          // Metadata will be preserved automatically by request interceptor
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
  update: (id: string, data: { email?: string; name?: string; role?: string; active?: boolean }) =>
    api.put(`/api/v1/users/${id}`, data),
  delete: (id: string) => api.delete(`/api/v1/users/${id}`),
  resendInvitation: (id: string) =>
    api.post(`/api/v1/users/${id}/resend-invitation`, {}),
  getProfile: () =>
    api.get('/api/v1/users/me'),
  updateProfile: (data: { name?: string; timezone?: string }) =>
    api.put('/api/v1/users/me', data),
  getToolsPreferences: () =>
    api.get('/api/v1/users/me/tools'),
  updateToolsPreferences: (enabledTools: string[]) =>
    api.put('/api/v1/users/me/tools', { enabled_tools: enabledTools }),
  getBackgroundServicesPreferences: () =>
    api.get('/api/v1/users/me/background-services'),
  updateBackgroundServicesPreferences: (data: { email_notifications_enabled?: boolean; calendar_notifications_enabled?: boolean }) =>
    api.put('/api/v1/users/me/background-services', data),
  getOAuthIntegrations: () =>
    api.get('/api/v1/users/me/oauth-integrations'),
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
  chat: (id: string, message: string, proceedWithNewDay: boolean = false) =>
    api.post(`/api/sessions/${id}/chat`, { message, session_id: id, use_memory: true, force_web_search: false, proceed_with_new_day: proceedWithNewDay }, { timeout: 600000 }), // 10 minutes to allow long-running operations (Gmail API, LangGraph, tool execution)
  getMemory: (id: string) => api.get(`/api/sessions/${id}/memory`, { timeout: 30000 }), // 30 seconds
  cleanContradictionNotifications: () => api.delete('/api/sessions/notifications/contradictions'),
}

// Notifications API
export const notificationsApi = {
  list: (params?: {
    session_id?: string
    urgency?: string
    read?: boolean
    limit?: number
    offset?: number
  }) => api.get('/api/notifications/', { params, timeout: 30000 }), // 30 seconds timeout
  count: (params?: {
    session_id?: string
    urgency?: string
    read?: boolean
  }) => api.get('/api/notifications/count', { params, timeout: 30000 }), // 30 seconds timeout
  markRead: (notificationId: string) => api.post(`/api/notifications/${notificationId}/read`, null, { timeout: 30000 }),
  markAllRead: (params?: { session_id?: string; urgency?: string }) =>
    api.post('/api/notifications/read-all', null, { params, timeout: 30000 }), // 30 seconds timeout
  delete: (notificationId: string) => api.delete(`/api/notifications/${notificationId}`, { timeout: 30000 }),
  deleteBatch: (notificationIds: string[]) =>
    api.post('/api/notifications/batch/delete', notificationIds, { timeout: 30000 }), // 30 seconds timeout
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
  list: (sessionId: string) => api.get(`/api/files/session/${sessionId}`, { timeout: 30000 }), // 30 seconds
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
  listLongTerm: (limit: number = 100, offset: number = 0, minImportance?: number) =>
    api.get('/api/memory/long/list', { params: { limit, offset, min_importance: minImportance } }),
  deleteLongTermBatch: (memoryIds: string[]) =>
    api.post('/api/memory/long/batch/delete', { memory_ids: memoryIds }),
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
        authorize: (integrationId?: string, serviceIntegration?: boolean) => {
          const params: any = {}
          if (integrationId) params.integration_id = integrationId
          if (serviceIntegration) params.service_integration = true
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
        listServiceIntegrations: (provider?: string) => {
          const params = provider ? { provider } : {}
          return api.get('/api/integrations/calendars/admin/integrations', { params })
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
    updateIntegration: (integrationId: string, name: string) =>
      api.put(`/api/integrations/mcp/integrations/${integrationId}`, { name }),
    test: (integrationId: string) => api.post(`/api/integrations/mcp/${integrationId}/test`, { timeout: 45000 }),
    debug: (integrationId: string) => api.get(`/api/integrations/mcp/${integrationId}/debug`),
    authorize: (integrationId: string) =>
      api.get(`/api/integrations/mcp/${integrationId}/oauth/authorize`),
    revoke: (integrationId: string) =>
      api.delete(`/api/integrations/mcp/${integrationId}/oauth/revoke`),
  },
  email: {
        authorize: (integrationId?: string, serviceIntegration?: boolean) => {
          const params: any = {}
          if (integrationId) params.integration_id = integrationId
          if (serviceIntegration) params.service_integration = true
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

