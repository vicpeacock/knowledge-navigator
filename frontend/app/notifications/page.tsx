'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { notificationsApi } from '@/lib/api'
import { Bell, Filter, X, CheckCircle2, Trash2, AlertCircle, Mail, Calendar, MessageSquare, ArrowLeft } from 'lucide-react'
import { format } from 'date-fns'

interface Notification {
  id: string
  type: string
  urgency: string
  content: {
    message?: string
    title?: string
    subject?: string
    from?: string
    snippet?: string
    email_id?: string
    session_id?: string
    session_link?: string
    has_session?: boolean
    summary?: string
    start_time?: string
    end_time?: string
    event_id?: string
  }
  session_id?: string | null
  read: boolean
  created_at: string
}

export default function NotificationsPage() {
  const router = useRouter()
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [filters, setFilters] = useState({
    urgency: '' as '' | 'high' | 'medium' | 'low',
    type: '' as '' | 'email_received' | 'calendar_event_starting' | 'contradiction' | 'todo',
    read: false,
  })
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const limit = 50

  const loadNotifications = useCallback(async () => {
    setLoading(true)
    try {
      const params: any = {
        read: filters.read,
        limit,
        offset,
      }
      if (filters.urgency) params.urgency = filters.urgency
      if (filters.type) params.type = filters.type

      const [listResponse, countResponse] = await Promise.all([
        notificationsApi.list(params),
        notificationsApi.count({ read: filters.read }),
      ])

      setNotifications(listResponse.data || [])
      setTotal(countResponse.data?.count || 0)
    } catch (error: any) {
      console.error('Error loading notifications:', error)
    } finally {
      setLoading(false)
    }
  }, [filters, offset])

  useEffect(() => {
    loadNotifications()
  }, [loadNotifications])

  const handleSelectAll = () => {
    if (selectedIds.size === notifications.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(notifications.map(n => n.id)))
    }
  }

  const handleSelectItem = (id: string) => {
    const newSelected = new Set(selectedIds)
    if (newSelected.has(id)) {
      newSelected.delete(id)
    } else {
      newSelected.add(id)
    }
    setSelectedIds(newSelected)
  }

  const handleMarkRead = async (id: string) => {
    try {
      await notificationsApi.markRead(id)
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, read: true } : n))
    } catch (error) {
      console.error('Error marking notification as read:', error)
    }
  }

  const handleMarkAllRead = async () => {
    try {
      await notificationsApi.markAllRead()
      await loadNotifications()
    } catch (error) {
      console.error('Error marking all as read:', error)
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await notificationsApi.delete(id)
      setNotifications(prev => prev.filter(n => n.id !== id))
      setSelectedIds(prev => {
        const newSet = new Set(prev)
        newSet.delete(id)
        return newSet
      })
    } catch (error) {
      console.error('Error deleting notification:', error)
    }
  }

  const handleDeleteBatch = async () => {
    if (selectedIds.size === 0) return
    if (!confirm(`Vuoi eliminare ${selectedIds.size} notifiche selezionate?`)) return

    try {
      await notificationsApi.deleteBatch(Array.from(selectedIds))
      setSelectedIds(new Set())
      await loadNotifications()
    } catch (error) {
      console.error('Error deleting notifications:', error)
    }
  }

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case 'email_received':
        return <Mail size={16} className="text-blue-600" />
      case 'calendar_event_starting':
        return <Calendar size={16} className="text-green-600" />
      case 'contradiction':
        return <AlertCircle size={16} className="text-red-600" />
      default:
        return <Bell size={16} className="text-gray-600" />
    }
  }

  const getUrgencyColor = (urgency: string) => {
    switch (urgency) {
      case 'high':
        return 'bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400'
      case 'medium':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400'
      case 'low':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
    }
  }

  return (
    <div className="min-h-screen p-8 bg-gray-50 dark:bg-gray-900">
      <div className="max-w-6xl mx-auto">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg">
          {/* Header */}
          <div className="p-6 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <button
                  onClick={() => router.back()}
                  className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                  title="Torna indietro"
                >
                  <ArrowLeft size={20} className="text-gray-600 dark:text-gray-400" />
                </button>
                <Bell size={24} className="text-blue-600 dark:text-blue-400" />
                <h1 className="text-2xl font-bold">Notifiche</h1>
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  {total} totali
                </span>
              </div>
              <div className="flex items-center gap-2">
                {selectedIds.size > 0 && (
                  <button
                    onClick={handleDeleteBatch}
                    className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 flex items-center gap-2"
                  >
                    <Trash2 size={16} />
                    Elimina Selezionate ({selectedIds.size})
                  </button>
                )}
                <button
                  onClick={handleMarkAllRead}
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 flex items-center gap-2"
                >
                  <CheckCircle2 size={16} />
                  Segna Tutte come Lette
                </button>
              </div>
            </div>

            {/* Filters */}
            <div className="flex items-center gap-4">
              <select
                value={filters.urgency}
                onChange={e => setFilters({ ...filters, urgency: e.target.value as any })}
                className="px-3 py-2 border rounded dark:bg-gray-700 dark:border-gray-600"
              >
                <option value="">Tutte le urgenze</option>
                <option value="high">Alta</option>
                <option value="medium">Media</option>
                <option value="low">Bassa</option>
              </select>
              <select
                value={filters.type}
                onChange={e => setFilters({ ...filters, type: e.target.value as any })}
                className="px-3 py-2 border rounded dark:bg-gray-700 dark:border-gray-600"
              >
                <option value="">Tutti i tipi</option>
                <option value="email_received">Email</option>
                <option value="calendar_event_starting">Calendario</option>
                <option value="contradiction">Contraddizioni</option>
                <option value="todo">Todo</option>
              </select>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={filters.read}
                  onChange={e => setFilters({ ...filters, read: e.target.checked })}
                  className="rounded"
                />
                <span className="text-sm">Incluse lette</span>
              </label>
            </div>
          </div>

          {/* Notifications List */}
          <div className="p-6">
            {loading ? (
              <div className="text-center py-12 text-gray-500">Caricamento...</div>
            ) : notifications.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                Nessuna notifica trovata
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center gap-2 mb-4">
                  <input
                    type="checkbox"
                    checked={selectedIds.size === notifications.length && notifications.length > 0}
                    onChange={handleSelectAll}
                    className="rounded"
                  />
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    Seleziona tutto
                  </span>
                </div>
                {notifications.map(notification => (
                  <div
                    key={notification.id}
                    className={`p-4 border rounded-lg flex items-start gap-3 ${
                      notification.read
                        ? 'bg-gray-50 dark:bg-gray-700/50 opacity-60'
                        : 'bg-white dark:bg-gray-800'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedIds.has(notification.id)}
                      onChange={() => handleSelectItem(notification.id)}
                      className="mt-1 rounded"
                    />
                    <div className="flex-1">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            {getNotificationIcon(notification.type)}
                            <span className="font-semibold">{notification.content.title || notification.type}</span>
                            <span className={`px-2 py-1 rounded text-xs ${getUrgencyColor(notification.urgency)}`}>
                              {notification.urgency}
                            </span>
                            {notification.read && (
                              <span className="text-xs text-gray-500">(letta)</span>
                            )}
                          </div>
                          <p className="text-sm text-gray-700 dark:text-gray-300 mb-2">
                            {notification.content.message || notification.content.snippet || notification.content.subject}
                          </p>
                          <div className="flex items-center gap-4 text-xs text-gray-500">
                            {notification.created_at && (
                              <span>{format(new Date(notification.created_at), 'dd/MM/yyyy HH:mm')}</span>
                            )}
                            {notification.content.from && (
                              <span>Da: {notification.content.from}</span>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {!notification.read && (
                            <button
                              onClick={() => handleMarkRead(notification.id)}
                              className="p-2 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded"
                              title="Segna come letta"
                            >
                              <CheckCircle2 size={16} />
                            </button>
                          )}
                          <button
                            onClick={() => handleDelete(notification.id)}
                            className="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
                            title="Elimina"
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Pagination */}
            {notifications.length > 0 && (
              <div className="flex items-center justify-between mt-6 pt-6 border-t">
                <button
                  onClick={() => setOffset(Math.max(0, offset - limit))}
                  disabled={offset === 0 || loading}
                  className="px-4 py-2 border rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50"
                >
                  Precedente
                </button>
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  {offset + 1}-{Math.min(offset + limit, total)} di {total}
                </span>
                <button
                  onClick={() => setOffset(offset + limit)}
                  disabled={offset + limit >= total || loading}
                  className="px-4 py-2 border rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50"
                >
                  Successivo
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

