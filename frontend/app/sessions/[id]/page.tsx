'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import ChatInterface from '@/components/ChatInterface'
import SessionList from '@/components/SessionList'
import SessionDetails from '@/components/SessionDetails'
import { AgentActivityProvider } from '@/components/AgentActivityContext'
import { sessionsApi } from '@/lib/api'
import { Session } from '@/types'

export default function SessionPage() {
  const params = useParams()
  const sessionId = params.id as string
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (sessionId) {
      loadSession()
    }
  }, [sessionId])

  const loadSession = async () => {
    try {
      const response = await sessionsApi.get(sessionId)
      setSession(response.data)
    } catch (error) {
      console.error('Error loading session:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex h-screen">
        <SessionList currentSessionId={sessionId} />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-gray-500">Loading session...</div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen">
      <SessionList currentSessionId={sessionId} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <AgentActivityProvider sessionId={sessionId}>
          {session && <SessionDetails session={session} onUpdate={loadSession} />}
          <div className="flex-1 overflow-hidden flex flex-col">
            <ChatInterface sessionId={sessionId} />
          </div>
        </AgentActivityProvider>
      </div>
    </div>
  )
}

