'use client'

import { useParams } from 'next/navigation'
import ChatInterface from '@/components/ChatInterface'
import SessionList from '@/components/SessionList'

export default function SessionPage() {
  const params = useParams()
  const sessionId = params.id as string

  return (
    <div className="flex h-screen">
      <SessionList currentSessionId={sessionId} />
      <div className="flex-1">
        <ChatInterface sessionId={sessionId} />
      </div>
    </div>
  )
}

