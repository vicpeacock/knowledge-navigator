'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { sessionsApi } from '@/lib/api'
import { Session } from '@/types'
import { Plus, Archive, RotateCcw, X } from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'

interface SessionListProps {
  currentSessionId?: string
}

export default function SessionList({ currentSessionId }: SessionListProps) {
  const [sessions, setSessions] = useState<Session[]>([])
  const [archivedSessions, setArchivedSessions] = useState<Session[]>([])
  const [showArchived, setShowArchived] = useState(false)
  const [loading, setLoading] = useState(true)
  const router = useRouter()
  const { isAuthenticated, isLoading: authLoading } = useAuth()

  useEffect(() => {
    // Wait for auth to complete before loading sessions
    if (!authLoading && isAuthenticated) {
      loadSessions()
    }
  }, [authLoading, isAuthenticated])

  const loadSessions = async () => {
    try {
      const [activeResponse, archivedResponse] = await Promise.all([
        sessionsApi.list('active'),
        sessionsApi.list('archived'),
      ])
      setSessions(activeResponse.data.filter((s: Session) => s.status === 'active'))
      setArchivedSessions(archivedResponse.data.filter((s: Session) => s.status === 'archived'))
    } catch (error) {
      console.error('Error loading sessions:', error)
    } finally {
      setLoading(false)
    }
  }

  const createNewSession = async () => {
    try {
      const response = await sessionsApi.create({
        name: `Session ${new Date().toLocaleString()}`,
      })
      if (response.data?.id) {
        // Refresh session list before navigating
        await loadSessions()
        router.push(`/sessions/${response.data.id}`)
      }
    } catch (error: any) {
      console.error('Error creating session:', error)
      alert(`Errore nella creazione della sessione: ${error.response?.data?.detail || error.message}`)
    }
  }

  if (loading) {
    return <div className="text-sm text-gray-500">Loading sessions...</div>
  }

  return (
    <div className="w-64 bg-gray-100 dark:bg-gray-900 p-4 h-screen flex flex-col overflow-y-auto pb-16">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Sessions</h2>
        <button
          onClick={createNewSession}
          className="p-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
          title="Crea nuova sessione"
        >
          <Plus size={16} />
        </button>
      </div>
      <div className="space-y-2 flex-1 overflow-y-auto">
        {sessions.map((session) => (
          <Link
            key={session.id}
            href={`/sessions/${session.id}`}
            className={`block p-3 rounded ${
              currentSessionId === session.id
                ? 'bg-blue-600 text-white'
                : 'bg-white dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700'
            }`}
          >
            <div className="font-medium truncate">{session.title || session.name}</div>
            {session.description && (
              <div className="text-xs mt-1 opacity-75 line-clamp-2">{session.description}</div>
            )}
            <div className="text-xs mt-1 opacity-75">
              {new Date(session.updated_at).toLocaleDateString()}
            </div>
          </Link>
        ))}
      </div>
      <div className="mt-4 pt-4 border-t border-gray-300 dark:border-gray-700">
        <button
          onClick={() => setShowArchived(!showArchived)}
          className="w-full px-3 py-2 text-sm bg-gray-700 dark:bg-gray-800 text-white rounded hover:bg-gray-600 dark:hover:bg-gray-700 transition-colors flex items-center justify-center gap-2"
        >
          {showArchived ? (
            <>
              <X size={16} />
              Hide Archived
            </>
          ) : (
            <>
              <Archive size={16} />
              Show Archived ({archivedSessions.length})
            </>
          )}
        </button>
        {showArchived && (
          <div className="mt-2 space-y-2 max-h-64 overflow-y-auto">
            {archivedSessions.length === 0 ? (
              <div className="text-sm text-gray-500 text-center py-4">No archived sessions</div>
            ) : (
              archivedSessions.map((session) => (
                <div
                  key={session.id}
                  className="p-3 rounded bg-gray-200 dark:bg-gray-800 border border-gray-300 dark:border-gray-700"
                >
                  <div className="font-medium truncate text-sm">{session.title || session.name}</div>
                  {session.description && (
                    <div className="text-xs mt-1 opacity-75 line-clamp-1">{session.description}</div>
                  )}
                  <div className="flex gap-2 mt-2">
                    <button
                      onClick={async (e) => {
                        e.preventDefault()
                        e.stopPropagation()
                        try {
                          await sessionsApi.restore(session.id)
                          loadSessions()
                        } catch (error: any) {
                          alert(`Error restoring: ${error.response?.data?.detail || error.message}`)
                        }
                      }}
                      className="flex-1 px-2 py-1 bg-green-600 text-white rounded hover:bg-green-700 text-xs flex items-center justify-center gap-1"
                    >
                      <RotateCcw size={12} />
                      Restore
                    </button>
                    <button
                      onClick={(e) => {
                        e.preventDefault()
                        e.stopPropagation()
                        router.push(`/sessions/${session.id}`)
                      }}
                      className="flex-1 px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 text-xs text-center transition-colors"
                    >
                      View
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}

