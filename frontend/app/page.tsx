'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { sessionsApi } from '@/lib/api'
import { Session } from '@/types'

export default function Dashboard() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadSessions()
  }, [])

  const loadSessions = async () => {
    try {
      console.log('Loading sessions from:', process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')
      const response = await sessionsApi.list()
      console.log('Sessions loaded:', response.data)
      setSessions(response.data)
    } catch (error: any) {
      console.error('Error loading sessions:', error)
      console.error('Error details:', error.response?.data || error.message)
      console.error('Error config:', error.config)
      // Set empty array on error to show UI
      setSessions([])
    } finally {
      setLoading(false)
    }
  }

  const createNewSession = async () => {
    try {
      console.log('Creating new session...')
      console.log('API URL:', process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')
      const response = await sessionsApi.create({
        name: `Session ${new Date().toLocaleString()}`,
      })
      console.log('Session created:', response.data)
      if (response.data?.id) {
        window.location.href = `/sessions/${response.data.id}`
      } else {
        console.error('No session ID in response:', response.data)
        alert('Errore: sessione creata ma ID non trovato. Verifica la console.')
      }
    } catch (error: any) {
      console.error('Error creating session:', error)
      console.error('Error response:', error.response)
      console.error('Error message:', error.message)
      console.error('Error config:', error.config)
      const errorMsg = error.response?.data?.detail || error.message || 'Errore sconosciuto'
      alert(`Errore nella creazione della sessione: ${errorMsg}\n\nVerifica la console per dettagli.`)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">Loading...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-6xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-4xl font-bold">Knowledge Navigator</h1>
          <div className="flex gap-3">
            <Link
              href="/integrations"
              className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700"
            >
              Integrazioni
            </Link>
            <button
              onClick={createNewSession}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              New Session
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {sessions.map((session) => (
            <Link
              key={session.id}
              href={`/sessions/${session.id}`}
              className="block p-6 bg-white dark:bg-gray-800 rounded-lg shadow hover:shadow-lg transition"
            >
              <h2 className="text-xl font-semibold mb-2">{session.name}</h2>
              <p className="text-sm text-gray-500">
                Updated: {new Date(session.updated_at).toLocaleString()}
              </p>
            </Link>
          ))}
        </div>

        {sessions.length === 0 && (
          <div className="text-center mt-12">
            <p className="text-gray-500 mb-4">No sessions yet. Create one to get started!</p>
            <button
              onClick={createNewSession}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Create Your First Session
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

