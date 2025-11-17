'use client'

import { useEffect, useState, useRef } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { sessionsApi } from '@/lib/api'
import { Session } from '@/types'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { useAuth } from '@/contexts/AuthContext'
import { Menu, X, User, Users, BarChart3, LogOut, Settings } from 'lucide-react'

function DashboardContent() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)
  const [menuOpen, setMenuOpen] = useState(false)
  const { user, logout } = useAuth()
  const router = useRouter()
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    loadSessions()
  }, [])

  // Chiudi menu quando si clicca fuori
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false)
      }
    }

    if (menuOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [menuOpen])

  const loadSessions = async () => {
    try {
      console.log('Loading sessions from:', process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')
      const response = await sessionsApi.list('active')  // Only load active sessions
      console.log('Sessions loaded:', response.data)
      // Filter to ensure only active sessions are shown
      setSessions(response.data.filter((s: Session) => s.status === 'active'))
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
          <div className="flex gap-3 items-center">
            <button
              onClick={createNewSession}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              New Session
            </button>
            {user && (
              <div className="relative" ref={menuRef}>
                <button
                  onClick={() => setMenuOpen(!menuOpen)}
                  className="p-2 rounded-lg bg-gray-700 dark:bg-gray-800 text-white hover:bg-gray-600 dark:hover:bg-gray-700 transition-colors"
                  aria-label="Menu"
                >
                  {menuOpen ? <X size={20} /> : <Menu size={20} />}
                </button>
                {menuOpen && (
                  <div className="absolute right-0 mt-2 w-56 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-2 z-50">
                    <div className="px-4 py-2 border-b border-gray-200 dark:border-gray-700">
                      <p className="text-sm font-semibold text-gray-900 dark:text-white">
                        {user.name || user.email}
                      </p>
                      {user.role === 'admin' && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Admin</p>
                      )}
                    </div>
                    <button
                      onClick={() => {
                        router.push('/settings/profile')
                        setMenuOpen(false)
                      }}
                      className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2 transition-colors"
                    >
                      <User size={16} />
                      Profile
                    </button>
                    <button
                      onClick={() => {
                        router.push('/integrations')
                        setMenuOpen(false)
                      }}
                      className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2 transition-colors"
                    >
                      <Settings size={16} />
                      Integrazioni
                    </button>
                    {user.role === 'admin' && (
                      <>
                        <button
                          onClick={() => {
                            router.push('/admin/users')
                            setMenuOpen(false)
                          }}
                          className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2 transition-colors"
                        >
                          <Users size={16} />
                          Admin
                        </button>
                        <button
                          onClick={() => {
                            router.push('/admin/metrics')
                            setMenuOpen(false)
                          }}
                          className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2 transition-colors"
                        >
                          <BarChart3 size={16} />
                          Metrics
                        </button>
                      </>
                    )}
                    <div className="border-t border-gray-200 dark:border-gray-700 mt-2 pt-2">
                      <button
                        onClick={() => {
                          logout()
                          setMenuOpen(false)
                        }}
                        className="w-full px-4 py-2 text-left text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 flex items-center gap-2 transition-colors"
                      >
                        <LogOut size={16} />
                        Logout
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {sessions.map((session) => (
            <Link
              key={session.id}
              href={`/sessions/${session.id}`}
              className="block p-6 bg-white dark:bg-gray-800 rounded-lg shadow hover:shadow-lg transition"
            >
              <h2 className="text-xl font-semibold mb-2">{session.title || session.name}</h2>
              {session.description && (
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-2 line-clamp-2">{session.description}</p>
              )}
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

export default function Dashboard() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  )
}

