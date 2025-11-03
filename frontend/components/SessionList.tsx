'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { sessionsApi } from '@/lib/api'
import { Session } from '@/types'
import { Plus } from 'lucide-react'

interface SessionListProps {
  currentSessionId?: string
}

export default function SessionList({ currentSessionId }: SessionListProps) {
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    loadSessions()
  }, [])

  const loadSessions = async () => {
    try {
      const response = await sessionsApi.list()
      setSessions(response.data)
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
    <div className="w-64 bg-gray-100 dark:bg-gray-900 p-4 h-screen overflow-y-auto flex flex-col">
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
      <div className="mb-4">
        <Link
          href="/integrations"
          className="block w-full px-3 py-2 text-sm bg-gray-700 dark:bg-gray-800 text-white rounded hover:bg-gray-600 dark:hover:bg-gray-700 transition-colors text-center"
        >
          ⚙️ Integrazioni
        </Link>
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
            <div className="font-medium truncate">{session.name}</div>
            <div className="text-xs mt-1 opacity-75">
              {new Date(session.updated_at).toLocaleDateString()}
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}

