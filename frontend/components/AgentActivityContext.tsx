'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { AgentActivityEvent, AgentActivityStatus } from '@/types'

interface AgentStatusSummary {
  agentId: string
  agentName: string
  status: AgentActivityStatus | 'idle'
  message?: string
  timestamp?: string
}

type ConnectionState = 'connecting' | 'open' | 'closed'

interface AgentActivityContextValue {
  events: AgentActivityEvent[]
  agentStatuses: AgentStatusSummary[]
  connectionState: ConnectionState
  ingestBatch: (events: AgentActivityEvent[] | undefined | null) => void
  reset: () => void
}

const AgentActivityContext = createContext<AgentActivityContextValue | undefined>(undefined)

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const AGENT_ORDER = [
  'event_handler',
  'orchestrator',
  'planner',
  'tool_loop',
  'knowledge_agent',
  'background_integrity_agent',
  'task_scheduler',
  'task_dispatcher',
  'notification_collector',
  'response_formatter',
]

const ACTIVE_WINDOW_MS = 1500
const WAITING_WINDOW_MS = 12000
const ERROR_WINDOW_MS = 15000
const COMPLETED_WINDOW_MS = 4000

function normaliseEvent(raw: any): AgentActivityEvent | null {
  if (!raw || typeof raw !== 'object') return null
  const { agent_id, agentId, agent_name, agentName, status, message, timestamp } = raw
  if (!agent_id && !agentId) return null
  if (!status || !timestamp) return null
  return {
    agent_id: agent_id || agentId,
    agent_name: agent_name || agentName || (agent_id || agentId),
    status,
    message: message ?? undefined,
    timestamp,
  }
}

export function AgentActivityProvider({ sessionId, children }: { sessionId: string; children: ReactNode }) {
  const [events, setEvents] = useState<AgentActivityEvent[]>([])
  const [connectionState, setConnectionState] = useState<ConnectionState>('connecting')
  const eventKeysRef = useRef<Set<string>>(new Set())
  const eventSourceRef = useRef<EventSource | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isUnmountedRef = useRef(false)

  const reset = useCallback(() => {
    eventKeysRef.current = new Set()
    setEvents([])
  }, [])

  const ingestBatch = useCallback(
    (incoming: AgentActivityEvent[] | null | undefined) => {
      if (!incoming || incoming.length === 0) return
      setEvents((prev) => {
        const next = [...prev]
        let changed = false
        for (const evt of incoming) {
          if (!evt.timestamp) continue
          const key = `${evt.timestamp}|${evt.agent_id}|${evt.status}`
          if (!eventKeysRef.current.has(key)) {
            eventKeysRef.current.add(key)
            next.push(evt)
            changed = true
          }
        }
        if (!changed) return prev
        next.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
        return next
      })
    },
    []
  )

  const connectStream = useCallback(() => {
    if (!sessionId) return

    if (eventSourceRef.current) {
      eventSourceRef.current.onopen = null
      eventSourceRef.current.onerror = null
      eventSourceRef.current.onmessage = null
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }

    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }

    setConnectionState('connecting')

    const streamUrl = `${API_BASE_URL}/api/sessions/${sessionId}/agent-activity/stream`
    console.log('[AgentActivity] Connecting to SSE stream:', streamUrl)
    const source = new EventSource(streamUrl)

    source.onopen = () => {
      console.log('[AgentActivity] SSE connection opened')
      setConnectionState('open')
    }

    source.onerror = (error) => {
      console.error('[AgentActivity] SSE connection error:', error)
      source.close()
      setConnectionState('closed')
      if (!isUnmountedRef.current && !reconnectTimerRef.current) {
        reconnectTimerRef.current = setTimeout(() => {
          reconnectTimerRef.current = null
          connectStream()
        }, 3000)
      }
    }

    source.onmessage = (event: MessageEvent<string>) => {
      if (!event.data) return
      try {
        const payload = JSON.parse(event.data)
        console.log('[AgentActivity] Received SSE event:', payload.type, payload.event?.agent_id)
        if (payload.type === 'agent_activity_snapshot' && Array.isArray(payload.events)) {
          const normalised = payload.events
            .map(normaliseEvent)
            .filter((evt: AgentActivityEvent | null): evt is AgentActivityEvent => evt !== null)
          console.log('[AgentActivity] Processing snapshot with', normalised.length, 'events')
          reset()
          ingestBatch(normalised)
          return
        }
        if (payload.type === 'agent_activity' && payload.event) {
          const evt = normaliseEvent(payload.event)
          if (evt) {
            console.log('[AgentActivity] Processing event:', evt.agent_id, evt.status)
            ingestBatch([evt])
          }
        }
      } catch (error) {
        console.error('[AgentActivity] Failed to parse SSE payload', error)
      }
    }

    eventSourceRef.current = source
  }, [ingestBatch, reset, sessionId])

  useEffect(() => {
    isUnmountedRef.current = false
    reset()
    connectStream()
    return () => {
      isUnmountedRef.current = true
      if (eventSourceRef.current) {
        eventSourceRef.current.onopen = null
        eventSourceRef.current.onerror = null
        eventSourceRef.current.onmessage = null
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      setConnectionState('closed')
    }
  }, [connectStream, reset, sessionId])

  const agentStatuses = useMemo(() => {
    const eventsByAgent = new Map<string, AgentActivityEvent[]>()
    events.forEach((evt) => {
      const list = eventsByAgent.get(evt.agent_id)
      if (list) {
        list.push(evt)
      } else {
        eventsByAgent.set(evt.agent_id, [evt])
      }
    })

    const now = Date.now()

    const toTitle = (agentId: string) => agentId.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

    const deriveStatus = (
      agentId: string,
      agentNameFallback: string,
      history: AgentActivityEvent[]
    ): AgentStatusSummary => {
      if (history.length === 0) {
        return {
          agentId,
          agentName: agentNameFallback,
          status: 'idle',
        }
      }

      let fallback: AgentStatusSummary | null = null

      for (let i = history.length - 1; i >= 0; i -= 1) {
        const evt = history[i]
        const evtTime = new Date(evt.timestamp).getTime()
        const age = Number.isFinite(evtTime) ? now - evtTime : Number.POSITIVE_INFINITY

        const summaryBase: AgentStatusSummary = {
          agentId,
          agentName: evt.agent_name || agentNameFallback,
          status: evt.status,
          message: evt.message,
          timestamp: evt.timestamp,
        }

        if (evt.status === 'error' && age <= ERROR_WINDOW_MS) {
          return summaryBase
        }
        if (evt.status === 'waiting' && age <= WAITING_WINDOW_MS) {
          return summaryBase
        }
        if (evt.status === 'started' && age <= ACTIVE_WINDOW_MS) {
          return summaryBase
        }
        if (!fallback) {
          fallback = summaryBase
        }
      }

      if (fallback) {
        if (fallback.status === 'completed' && fallback.timestamp) {
          const completedTime = new Date(fallback.timestamp).getTime()
          const completedAge = Number.isFinite(completedTime) ? now - completedTime : Number.POSITIVE_INFINITY
          if (completedAge > COMPLETED_WINDOW_MS) {
            return {
              agentId,
              agentName: fallback.agentName,
              status: 'idle',
            }
          }
        }
        return fallback
      }

      return {
        agentId,
        agentName: agentNameFallback,
        status: 'idle',
      }
    }

    const allAgentIds = Array.from(new Set([...AGENT_ORDER, ...Array.from(eventsByAgent.keys())]))

    return allAgentIds.map((agentId) => {
      const history = eventsByAgent.get(agentId) ?? []
      const fallbackName =
        history.length > 0
          ? history[history.length - 1].agent_name || toTitle(agentId)
          : toTitle(agentId)
      return deriveStatus(agentId, fallbackName, history)
    })
  }, [events])

  const contextValue = useMemo(
    () => ({
      events,
      agentStatuses,
      connectionState,
      ingestBatch,
      reset,
    }),
    [agentStatuses, connectionState, events, ingestBatch, reset]
  )

  return <AgentActivityContext.Provider value={contextValue}>{children}</AgentActivityContext.Provider>
}

export function useAgentActivity(): AgentActivityContextValue {
  const context = useContext(AgentActivityContext)
  if (!context) {
    throw new Error('useAgentActivity must be used within an AgentActivityProvider')
  }
  return context
}


