'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { Bell } from 'lucide-react'
import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Notification {
  id: string
  type: string
  priority: string
  created_at: string
  content: {
    message: string
    title?: string
    new_statement?: string
    contradictions?: Array<{
      existing_memory?: string
      explanation?: string
    }>
  }
}

interface NotificationBellProps {
  sessionId: string
}

export default function NotificationBell({ sessionId }: NotificationBellProps) {
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
      const response = await axios.get(
        `${API_URL}/api/sessions/${sessionId}/notifications/pending`,
        { timeout: 5000 } // 5 secondi timeout
      )
      setNotifications(response.data || [])
      
      // Restore scroll position after update
      if (scrollContainer && scrollTop > 0) {
        setTimeout(() => {
          scrollContainer.scrollTop = scrollTop
        }, 0)
      }
    } catch (error: any) {
      console.error('Error fetching notifications:', error)
      // Se è un errore di timeout o di rete, mantieni le notifiche esistenti
      if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        console.warn('Request timeout, keeping existing notifications')
      } else {
        // Per altri errori, svuota le notifiche
        setNotifications([])
      }
    } finally {
      setLoading(false)
      fetchingRef.current = false
    }
  }, [sessionId])

  useEffect(() => {
    if (sessionId && !isOpen) {
      // Only poll when popup is closed
      fetchNotifications()
      const interval = setInterval(fetchNotifications, 10000)
      return () => clearInterval(interval)
    } else if (sessionId && isOpen) {
      // Fetch once when popup opens
      fetchNotifications()
    }
  }, [sessionId, isOpen, fetchNotifications])

  const handleResolve = async (notificationId: string, resolution: string) => {
    // Save scroll position before update
    const scrollContainer = scrollContainerRef.current
    const scrollTop = scrollContainer?.scrollTop || 0
    
    try {
      await axios.post(
        `${API_URL}/api/sessions/${sessionId}/notifications/${notificationId}/resolve`,
        { resolution }
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
            className="fixed top-16 right-4 w-96 max-h-[80vh] bg-white dark:bg-gray-800 rounded-lg shadow-xl z-[120] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
              <h3 className="text-lg font-semibold">Notifiche</h3>
              <div className="flex items-center gap-2">
                {pendingCount > 0 && (
                  <button
                    type="button"
                    onClick={async (e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      if (confirm(`Vuoi eliminare tutte le ${pendingCount} notifiche pendenti?`)) {
                        try {
                          console.log('[NotificationBell] Cleaning contradiction notifications...')
                          console.log('[NotificationBell] API URL:', `${API_URL}/api/sessions/notifications/contradictions`)
                          const response = await axios.delete(`${API_URL}/api/sessions/notifications/contradictions`, {
                            timeout: 5000
                          })
                          console.log('[NotificationBell] Clean response status:', response.status)
                          console.log('[NotificationBell] Clean response data:', response.data)
                          
                          if (response.data && response.data.deleted_count !== undefined) {
                            // Clear notifications immediately
                            setNotifications([])
                            console.log(`[NotificationBell] ✅ Deleted ${response.data.deleted_count} notifications`)
                            
                            // Force refresh after a short delay to ensure backend has processed
                            setTimeout(() => {
                              console.log('[NotificationBell] Refreshing notifications...')
                              fetchNotifications()
                            }, 1000)
                          } else {
                            console.warn('[NotificationBell] Unexpected response format:', response.data)
                            setNotifications([])
                            setTimeout(() => fetchNotifications(), 1000)
                          }
                        } catch (error: any) {
                          console.error('[NotificationBell] Error cleaning notifications:', error)
                          if (error.response) {
                            console.error('[NotificationBell] Error status:', error.response.status)
                            console.error('[NotificationBell] Error data:', error.response.data)
                            alert(`Errore ${error.response.status}: ${error.response.data?.detail || error.response.data?.message || 'Errore sconosciuto'}`)
                          } else if (error.request) {
                            console.error('[NotificationBell] No response received:', error.request)
                            alert('Errore: il backend non ha risposto. Verifica che sia in esecuzione.')
                          } else {
                            console.error('[NotificationBell] Error setting up request:', error.message)
                            alert(`Errore: ${error.message}`)
                          }
                        }
                      }
                    }}
                    className="text-xs px-2 py-1 bg-red-500 text-white rounded hover:bg-red-600 transition-colors"
                    title="Elimina tutte le notifiche pendenti"
                  >
                    Pulisci
                  </button>
                )}
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    setIsOpen(false)
                  }}
                  className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                >
                  ✕
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
                  {notifications.map((notification) => (
                    <NotificationItem
                      key={notification.id}
                      notification={notification}
                      onResolve={(resolution) =>
                        handleResolve(notification.id, resolution)
                      }
                    />
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
  notification,
  onResolve,
}: {
  notification: Notification
  onResolve: (resolution: string) => void
}) {
  const [resolution, setResolution] = useState('')
  const [showOptions, setShowOptions] = useState(false)

  if (notification.type === 'contradiction') {
    return (
      <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
        <h4 className="font-semibold mb-2">
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
              className="flex-1 px-3 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 text-sm"
            >
              Risolvi
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                onResolve('ignore')
              }}
              className="px-3 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-300 dark:hover:bg-gray-600 text-sm"
            >
              Ignora
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
                className="flex-1 px-3 py-2 bg-green-500 text-white rounded hover:bg-green-600 text-sm"
                disabled={!resolution.trim()}
              >
                Conferma
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  setResolution('')
                  setShowOptions(false)
                }}
                className="px-3 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-300 dark:hover:bg-gray-600 text-sm"
              >
                Annulla
              </button>
            </div>
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                onResolve('no_contradiction')
              }}
              className="w-full px-3 py-2 bg-yellow-500 text-white rounded hover:bg-yellow-600 text-sm"
            >
              Non c&apos;è contraddizione
            </button>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
      <p className="text-sm">{notification.content.message}</p>
    </div>
  )
}

