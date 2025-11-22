'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { Bell, CheckCheck, Trash2, Eye, X, CheckCircle, XCircle, AlertCircle } from 'lucide-react'
import axios from 'axios'
import { sessionsApi } from '@/lib/api'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Notification {
  id: string
  type: string
  priority: string
  created_at: string
  session_id?: string | null
  content: {
    message: string
    title?: string
    new_statement?: string
    contradictions?: Array<{
      existing_memory?: string
      explanation?: string
    }>
    // Email-specific
    subject?: string
    from?: string
    snippet?: string
    email_id?: string
    session_id?: string
    auto_session_id?: string
    session_link?: string
    has_session?: boolean
    // Calendar-specific
    summary?: string
    start_time?: string
    end_time?: string
    event_id?: string
  }
}

interface NotificationBellProps {
  sessionId: string
}

export default function NotificationBell({ sessionId }: NotificationBellProps) {
  const router = useRouter()
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const fetchingRef = useRef(false)

  const fetchNotifications = useCallback(async () => {
    if (!sessionId || fetchingRef.current) return
    
    fetchingRef.current = true
    
    // Save scroll position before update
    const scrollContainer = scrollContainerRef.current
    const scrollTop = scrollContainer?.scrollTop || 0
    
    setLoading(true)
    try {
      // Use axios with authentication headers
      const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null
      const headers = token ? { Authorization: `Bearer ${token}` } : {}
      
      console.log(`[NotificationBell] Fetching notifications for session ${sessionId}...`)
      const startTime = Date.now()
      const response = await axios.get(
        `${API_URL}/api/sessions/${sessionId}/notifications/pending?limit=100`,
        { 
          headers,
          timeout: 30000 // 30 secondi timeout - aumentato per operazioni lente
        }
      )
      const elapsed = Date.now() - startTime
      console.log(`[NotificationBell] Received ${response.data?.length || 0} notifications in ${elapsed}ms`)
      setNotifications(response.data || [])
      
      // Restore scroll position after update
      if (scrollContainer && scrollTop > 0) {
        setTimeout(() => {
          scrollContainer.scrollTop = scrollTop
        }, 0)
      }
    } catch (error: any) {
      console.error('[NotificationBell] Error fetching notifications:', error)
      const status = error.response?.status
      const errorCode = error.code
      const errorMessage = error.message || ''
      
      // Mantieni le notifiche esistenti per la maggior parte degli errori
      // Svuota solo se l'errore indica che le notifiche non sono più valide
      if (
        status === 401 || // Unauthorized - l'utente non è più autenticato
        status === 403 || // Forbidden - l'utente non ha più accesso
        status === 404    // Not Found - la sessione non esiste più
      ) {
        console.warn(`[NotificationBell] Clearing notifications due to ${status} error (auth/session issue)`)
        setNotifications([])
      } else if (errorCode === 'ECONNABORTED' || errorMessage.includes('timeout')) {
        // Timeout: mantieni le notifiche esistenti
        console.warn('[NotificationBell] Request timeout, keeping existing notifications')
      } else {
        // Altri errori (500, network, etc.): mantieni le notifiche esistenti
        // Non svuotare perché potrebbero essere errori temporanei
        console.warn(`[NotificationBell] Error ${status || errorCode || 'unknown'}, keeping existing notifications to avoid data loss`)
      }
    } finally {
      setLoading(false)
      fetchingRef.current = false
    }
  }, [sessionId])

  // SSE connection for real-time updates (when popup is open)
  useEffect(() => {
    if (!sessionId || !isOpen) return

    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null
    if (!token) return

    // Use EventSource for SSE (fallback to polling if SSE fails)
    let eventSource: EventSource | null = null
    let fallbackInterval: NodeJS.Timeout | null = null

    try {
      // Try SSE first
      const sseUrl = `${API_URL}/api/notifications/stream?token=${encodeURIComponent(token)}`
      eventSource = new EventSource(sseUrl)

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'notification_update') {
            console.log(`[NotificationBell] SSE update: received ${data.notifications?.length || 0} notifications`)
            setNotifications(data.notifications || [])
          } else if (data.type === 'error') {
            console.error('[NotificationBell] SSE error:', data.message)
            // Non svuotare le notifiche in caso di errore SSE, mantieni quelle esistenti
          }
        } catch (e) {
          console.error('[NotificationBell] Error parsing SSE message:', e)
          // Non svuotare le notifiche in caso di errore di parsing
        }
      }

      eventSource.onerror = (error) => {
        console.warn('SSE connection error, falling back to polling:', error)
        eventSource?.close()
        eventSource = null
        
        // Fallback to polling
        fetchNotifications()
        fallbackInterval = setInterval(fetchNotifications, 30000) // Poll every 30s when SSE fails
      }
    } catch (error) {
      console.warn('SSE not supported, using polling:', error)
      fetchNotifications()
      fallbackInterval = setInterval(fetchNotifications, 30000) // Poll every 30s when SSE not supported
    }

    return () => {
      eventSource?.close()
      if (fallbackInterval) clearInterval(fallbackInterval)
    }
  }, [sessionId, isOpen, fetchNotifications])

  // Initial fetch and polling when popup is closed
  useEffect(() => {
    if (sessionId && !isOpen) {
      // Fetch immediately when popup closes
      fetchNotifications()
      // Poll every 30s when closed (but don't clear notifications on error)
      const interval = setInterval(() => {
        console.log('[NotificationBell] Polling notifications (popup closed)')
        fetchNotifications()
      }, 30000) // Poll every 30s when closed
      return () => clearInterval(interval)
    } else if (sessionId && isOpen) {
      // Fetch once when popup opens (SSE will take over)
      console.log('[NotificationBell] Popup opened, fetching notifications')
      fetchNotifications()
    }
  }, [sessionId, isOpen, fetchNotifications])

  const handleResolve = async (notificationId: string, resolution: string) => {
    // Save scroll position before update
    const scrollContainer = scrollContainerRef.current
    const scrollTop = scrollContainer?.scrollTop || 0
    
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null
      const headers = token ? { Authorization: `Bearer ${token}` } : {}
      
      await axios.post(
        `${API_URL}/api/sessions/${sessionId}/notifications/${notificationId}/resolve`,
        { resolution },
        { headers }
      )
      // Remove notification from local list instead of full refresh
      setNotifications((prev) => prev.filter((n) => n.id !== notificationId))
      
      // Restore scroll position after update
      if (scrollContainer && scrollTop > 0) {
        setTimeout(() => {
          scrollContainer.scrollTop = scrollTop
        }, 0)
      }
    } catch (error) {
      console.error('Error resolving notification:', error)
      // On error, refresh to get current state
      await fetchNotifications()
    }
  }

  const handleDelete = async (notificationId: string) => {
    // Save scroll position before update
    const scrollContainer = scrollContainerRef.current
    const scrollTop = scrollContainer?.scrollTop || 0
    
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null
      const headers = token ? { Authorization: `Bearer ${token}` } : {}
      
      await axios.delete(`${API_URL}/api/notifications/${notificationId}`, { headers })
      // Remove notification from local list instead of full refresh
      setNotifications((prev) => prev.filter((n) => n.id !== notificationId))
      
      // Restore scroll position after update
      if (scrollContainer && scrollTop > 0) {
        setTimeout(() => {
          scrollContainer.scrollTop = scrollTop
        }, 0)
      }
    } catch (error) {
      console.error('Error deleting notification:', error)
      // On error, refresh to get current state
      await fetchNotifications()
      throw error // Re-throw to show error in UI
    }
  }

  const pendingCount = notifications.length

  return (
    <>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors"
        title="Notifiche"
      >
        <Bell size={20} />
        {pendingCount > 0 && (
          <span className="absolute top-0 right-0 bg-red-500 text-white text-xs rounded-full h-5 w-5 flex items-center justify-center">
            {pendingCount > 9 ? '9+' : pendingCount}
          </span>
        )}
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black bg-opacity-50 z-[110]"
            onClick={() => setIsOpen(false)}
          />
          
          {/* Popup */}
          <div
            className="fixed top-16 right-4 w-[500px] max-h-[80vh] bg-white dark:bg-gray-800 rounded-lg shadow-xl z-[120] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between bg-gradient-to-r from-gray-50 to-white dark:from-gray-800 dark:to-gray-800">
              <div className="flex items-center gap-3 flex-1 min-w-0">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Notifiche</h3>
                {pendingCount > 0 && (
                  <span className="text-sm text-gray-600 dark:text-gray-400 font-medium whitespace-nowrap">
                    {pendingCount} {pendingCount === 1 ? 'notifica' : 'notifiche'}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                {pendingCount > 0 && (
                  <>
                    <button
                      type="button"
                      onClick={async (e) => {
                        e.preventDefault()
                        e.stopPropagation()
                        try {
                          const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null
                          const headers = token ? { Authorization: `Bearer ${token}` } : {}
                          await axios.post(`${API_URL}/api/notifications/read-all`, null, { headers })
                          await fetchNotifications()
                        } catch (error) {
                          console.error('Error marking all as read:', error)
                        }
                      }}
                      className="flex items-center gap-1.5 text-sm text-gray-700 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
                      title="Segna tutte come lette"
                    >
                      <CheckCheck size={16} />
                      <span>Segna Lette</span>
                    </button>
                    <button
                      type="button"
                      onClick={async (e) => {
                        e.preventDefault()
                        e.stopPropagation()
                        if (confirm(`Vuoi eliminare tutte le ${pendingCount} notifiche pendenti?`)) {
                          try {
                            const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null
                            const headers = token ? { Authorization: `Bearer ${token}` } : {}
                            const ids = notifications.map(n => n.id)
                            await axios.post(`${API_URL}/api/notifications/batch/delete`, ids, { headers })
                            setNotifications([])
                            setTimeout(() => fetchNotifications(), 500)
                          } catch (error: any) {
                            console.error('[NotificationBell] Error cleaning notifications:', error)
                            alert(`Errore: ${error.response?.data?.detail || error.message || 'Errore sconosciuto'}`)
                          }
                        }
                      }}
                      className="flex items-center gap-1.5 text-sm text-gray-700 dark:text-gray-300 hover:text-red-600 dark:hover:text-red-400 transition-colors"
                      title="Elimina tutte le notifiche pendenti"
                    >
                      <Trash2 size={16} />
                      <span>Pulisci</span>
                    </button>
                  </>
                )}
                <a
                  href="/notifications"
                  className="flex items-center gap-1.5 text-sm text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 transition-colors"
                  title="Vedi tutte le notifiche"
                >
                  <Eye size={16} />
                  <span>Vedi Tutte</span>
                </a>
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    setIsOpen(false)
                  }}
                  className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
                  title="Chiudi"
                >
                  <X size={16} />
                </button>
              </div>
            </div>
            
            <div ref={scrollContainerRef} className="overflow-y-auto flex-1 p-4">
              {loading ? (
                <div className="text-center text-gray-500 py-4">Caricamento...</div>
              ) : notifications.length === 0 ? (
                <div className="text-center text-gray-500 py-4">
                  Nessuna notifica in attesa
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Group notifications by type */}
                  {Object.entries(
                    notifications.reduce((acc, notification) => {
                      const type = notification.type || 'other'
                      if (!acc[type]) acc[type] = []
                      acc[type].push(notification)
                      return acc
                    }, {} as Record<string, typeof notifications>)
                  ).map(([type, typeNotifications]) => (
                    <div key={type} className="space-y-2">
                      {typeNotifications.length > 1 && (
                        <div className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide px-2">
                          {type === 'email_received' && 'Email'}
                          {type === 'calendar_event_starting' && 'Calendario'}
                          {type === 'contradiction' && 'Contraddizioni'}
                          {type === 'todo' && 'Todo'}
                          {!['email_received', 'calendar_event_starting', 'contradiction', 'todo'].includes(type) && type}
                          {' '}({typeNotifications.length})
                        </div>
                      )}
                      {typeNotifications.map((notification) => (
                        <NotificationItem
                          key={notification.id}
                          notification={notification}
                          onResolve={(resolution) =>
                            handleResolve(notification.id, resolution)
                          }
                          onDelete={handleDelete}
                          onClose={() => setIsOpen(false)}
                          onNotificationUpdate={(notificationId, updates) => {
                            // Update notification in local state
                            setNotifications((prev) =>
                              prev.map((n) =>
                                n.id === notificationId ? { ...n, ...updates } : n
                              )
                            )
                          }}
                        />
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </>
  )
}

function NotificationItem({
  notification: initialNotification,
  onResolve,
  onDelete,
  onClose,
  onNotificationUpdate,
}: {
  notification: Notification
  onResolve: (resolution: string) => void
  onDelete: (notificationId: string) => void
  onClose?: () => void
  onNotificationUpdate?: (notificationId: string, updates: Partial<Notification>) => void
}) {
  const router = useRouter()
  const [notification, setNotification] = useState(initialNotification)
  const [resolution, setResolution] = useState('')
  const [showOptions, setShowOptions] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  
  // Update local notification state when prop changes
  useEffect(() => {
    setNotification(initialNotification)
  }, [initialNotification])

  const handleDelete = async (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (confirm('Vuoi eliminare questa notifica?')) {
      setIsDeleting(true)
      try {
        await onDelete(notification.id)
      } catch (error) {
        console.error('Error deleting notification:', error)
        alert('Errore durante l\'eliminazione della notifica')
      } finally {
        setIsDeleting(false)
      }
    }
  }

  if (notification.type === 'contradiction') {
    return (
      <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 relative">
        <button
          type="button"
          onClick={handleDelete}
          disabled={isDeleting}
          className="absolute top-2 right-2 text-gray-400 hover:text-red-500 transition-colors disabled:opacity-50"
          title="Elimina notifica"
        >
          <span className="text-lg font-bold">×</span>
        </button>
        <h4 className="font-semibold mb-2 pr-6">
          {notification.content.title || 'Contraddizione rilevata'}
        </h4>
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
          {notification.content.message}
        </p>
        
        {notification.content.new_statement && (
          <div className="mb-3">
            <p className="text-xs font-medium text-gray-500 mb-1">Nuova informazione:</p>
            <p className="text-sm bg-blue-50 dark:bg-blue-900/20 p-2 rounded">
              {notification.content.new_statement}
            </p>
          </div>
        )}

        {notification.content.contradictions && notification.content.contradictions.length > 0 && (
          <div className="mb-3">
            <p className="text-xs font-medium text-gray-500 mb-1">Memorie in conflitto:</p>
            {notification.content.contradictions.map((c, idx) => (
              <div key={idx} className="text-sm bg-red-50 dark:bg-red-900/20 p-2 rounded mb-2">
                {c.existing_memory && <p>{c.existing_memory}</p>}
                {c.explanation && (
                  <p className="text-xs text-gray-500 mt-1">{c.explanation}</p>
                )}
              </div>
            ))}
          </div>
        )}

        {!showOptions ? (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                setShowOptions(true)
              }}
              className="flex items-center gap-1.5 flex-1 text-sm text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 transition-colors"
            >
              <CheckCircle size={16} />
              <span>Risolvi</span>
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                onResolve('ignore')
              }}
              className="flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
            >
              <XCircle size={16} />
              <span>Ignora</span>
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            <textarea
              value={resolution}
              onChange={(e) => setResolution(e.target.value)}
              placeholder="Indica quale versione è corretta o fornisci un contesto per conciliare le informazioni..."
              className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded text-sm resize-none"
              rows={3}
            />
            <div className="flex gap-2">
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  onResolve(resolution || 'resolved')
                }}
                className="flex items-center gap-1.5 flex-1 text-sm text-green-600 dark:text-green-400 hover:text-green-700 dark:hover:text-green-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={!resolution.trim()}
              >
                <CheckCircle size={16} />
                <span>Conferma</span>
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  setResolution('')
                  setShowOptions(false)
                }}
                className="flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
              >
                <XCircle size={16} />
                <span>Annulla</span>
              </button>
            </div>
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                onResolve('no_contradiction')
              }}
              className="flex items-center gap-1.5 w-full text-sm text-yellow-600 dark:text-yellow-400 hover:text-yellow-700 dark:hover:text-yellow-300 transition-colors"
            >
              <AlertCircle size={16} />
              <span>Non c&apos;è contraddizione</span>
            </button>
          </div>
        )}
      </div>
    )
  }

  // Email or calendar notification with optional session link
  // Check for auto_session_id first (session created automatically from email analysis)
  // Then check for session_id in content or at notification level
  const sessionId = notification.content.auto_session_id || notification.content.session_id || notification.session_id
  const hasSession = !!sessionId || notification.content.has_session

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 relative">
      <button
        type="button"
        onClick={handleDelete}
        disabled={isDeleting}
        className="absolute top-2 right-2 text-gray-400 hover:text-red-500 transition-colors disabled:opacity-50"
        title="Elimina notifica"
      >
        <span className="text-lg font-bold">×</span>
      </button>
      <p className="text-sm mb-3 pr-6">{notification.content.message}</p>
      
      {/* Email-specific content */}
      {notification.type === 'email_received' && (
        <div className="mb-3 space-y-1">
          {notification.content.subject && (
            <p className="text-xs font-medium text-gray-600 dark:text-gray-400">
              Oggetto: {notification.content.subject}
            </p>
          )}
          {notification.content.snippet && (
            <p className="text-xs text-gray-500 dark:text-gray-500 line-clamp-2">
              {notification.content.snippet}
            </p>
          )}
        </div>
      )}
      
      {/* Calendar-specific content */}
      {notification.type === 'calendar_event_starting' && (
        <div className="mb-3 space-y-1">
          {notification.content.summary && (
            <p className="text-xs font-medium text-gray-600 dark:text-gray-400">
              {notification.content.summary}
            </p>
          )}
          {notification.content.start_time && (
            <p className="text-xs text-gray-500 dark:text-gray-500">
              Inizio: {new Date(notification.content.start_time).toLocaleString('it-IT')}
            </p>
          )}
        </div>
      )}
      
      {/* Session link button */}
      {hasSession && sessionId && (
        <button
          type="button"
          onClick={async (e) => {
            e.preventDefault()
            e.stopPropagation()
            
            // Verify session exists and is active before navigating
            try {
              // Use sessionsApi which includes authentication headers
              const response = await sessionsApi.get(sessionId)
              if (response.data && response.data.id) {
                // Check if session is active (not deleted or archived)
                if (response.data.status === 'active') {
                  // Session exists and is active, navigate to it
                  router.push(`/sessions/${sessionId}`)
                  // Close notification popup
                  if (onClose) {
                    onClose()
                  }
                } else {
                  // Session exists but is not active (deleted/archived), create new one
                  console.log(`Session ${sessionId} exists but status is ${response.data.status}, creating new one from notification...`)
                  await createSessionFromNotification()
                }
              } else {
                console.error('Session not found:', sessionId)
                // Try to create session from notification
                await createSessionFromNotification()
              }
            } catch (error: any) {
              console.error('Error verifying session:', error)
              if (error.response?.status === 404 || error.response?.status === 403) {
                // Session was deleted or not accessible, try to create a new one from notification
                console.log('Session not found or not accessible, attempting to create from notification...')
                await createSessionFromNotification()
              } else if (error.response?.status === 401) {
                alert(`Errore di autenticazione. Per favore, effettua il login.`)
              } else {
                alert(`Errore nel verificare la sessione: ${error.message}`)
              }
            }
            
            async function createSessionFromNotification() {
              try {
                const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null
                const headers = token ? { Authorization: `Bearer ${token}` } : {}
                
                const createResponse = await axios.post(
                  `${API_URL}/api/sessions/notifications/${notification.id}/create-session`,
                  {},
                  { headers }
                )
                
                if (createResponse.data && createResponse.data.id) {
                  const newSessionId = createResponse.data.id
                  
                  // Update notification content with new session_id
                  // This ensures next time we click "Apri Sessione", it uses the new session
                  const updatedNotification = {
                    ...notification,
                    content: {
                      ...notification.content,
                      auto_session_id: newSessionId,
                      session_id: newSessionId,
                      has_session: true,
                    },
                    session_id: newSessionId,
                  }
                  setNotification(updatedNotification)
                  
                  // Notify parent component to update notification
                  if (onNotificationUpdate) {
                    onNotificationUpdate(notification.id, updatedNotification)
                  }
                  
                  // Navigate to newly created session
                  router.push(`/sessions/${newSessionId}`)
                  // Close notification popup
                  if (onClose) {
                    onClose()
                  }
                  
                  // Refresh notifications to get updated data from backend
                  // This ensures the notification is updated with the new session_id
                  if (typeof window !== 'undefined' && window.location.pathname.includes('/sessions/')) {
                    // Only refresh if we're on a session page (to avoid unnecessary refresh)
                    setTimeout(() => {
                      // Trigger a refresh of notifications after navigation
                      // The parent component will refresh when popup is reopened
                    }, 1000)
                  }
                } else {
                  alert('Errore nella creazione della sessione dalla notifica.')
                }
              } catch (createError: any) {
                console.error('Error creating session from notification:', createError)
                alert(`Errore nella creazione della sessione: ${createError.response?.data?.detail || createError.message}`)
              }
            }
          }}
          className="flex items-center gap-1.5 w-full mt-3 text-sm text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 transition-colors"
        >
          <Eye size={16} />
          <span>Apri Sessione</span>
        </button>
      )}
    </div>
  )
}

