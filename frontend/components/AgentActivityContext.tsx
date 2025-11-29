'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { AgentActivityEvent, AgentActivityStatus } from '@/types'
import { useAuth } from '@/contexts/AuthContext'

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
  'event_monitor',
]

// Increased ACTIVE_WINDOW_MS to ensure "started" events are shown even for fast-executing agents
const ACTIVE_WINDOW_MS = 5000  // 5 seconds - enough time to see "in esecuzione" even for quick operations
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
  const { token, refreshToken } = useAuth()
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

  const connectStream = useCallback(async () => {
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

    // Try to get token from AuthContext, or refresh if needed
    let currentToken = token
    if (!currentToken && typeof window !== 'undefined') {
      // Fallback to localStorage if AuthContext token is not available
      currentToken = localStorage.getItem('access_token')
      
      // If still no token, try to refresh
      if (!currentToken && refreshToken) {
        try {
          console.log('[AgentActivity] No token available, attempting refresh...')
          currentToken = await refreshToken()
        } catch (error) {
          console.error('[AgentActivity] Failed to refresh token:', error)
          // Will try to connect without token (will fail with 401, but that's expected)
        }
      }
    }

    // EventSource doesn't support custom headers, so we pass token as query param
    const streamUrl = currentToken 
      ? `${API_BASE_URL}/api/sessions/${sessionId}/agent-activity/stream?token=${encodeURIComponent(currentToken)}`
      : `${API_BASE_URL}/api/sessions/${sessionId}/agent-activity/stream`
    console.log('[AgentActivity] Connecting to SSE stream:', streamUrl.replace(currentToken || '', '[TOKEN]'))
    console.log('[AgentActivity] Token present:', !!currentToken, 'Token length:', currentToken?.length || 0)
    const source = new EventSource(streamUrl)

    source.onopen = () => {
      console.log('[AgentActivity] ✅✅✅ SSE connection opened for session:', sessionId)
      setConnectionState('open')
    }

    source.onerror = async (error) => {
      console.error('[AgentActivity] ❌❌❌ SSE connection error:', error)
      console.error('[AgentActivity] Error details:', {
        readyState: source.readyState,
        url: streamUrl.replace(currentToken || '', '[TOKEN]'),
        sessionId,
      })
      source.close()
      setConnectionState('closed')
      
      // If 401 error and we have refreshToken, try to refresh before reconnecting
      if (source.readyState === EventSource.CLOSED && refreshToken && !currentToken) {
        try {
          console.log('[AgentActivity] 401 error detected, attempting token refresh before reconnect...')
          await refreshToken()
          // Token refreshed, reconnect immediately
          if (!isUnmountedRef.current && !reconnectTimerRef.current) {
            reconnectTimerRef.current = setTimeout(() => {
              reconnectTimerRef.current = null
              console.log('[AgentActivity] 🔄 Reconnecting SSE stream after token refresh...')
              connectStream().catch((err) => {
                console.error('[AgentActivity] Error reconnecting after refresh:', err)
              })
            }, 1000) // Shorter delay after refresh
          }
          return
        } catch (refreshError) {
          console.error('[AgentActivity] Token refresh failed:', refreshError)
          // Continue with normal reconnect logic
        }
      }
      
      if (!isUnmountedRef.current && !reconnectTimerRef.current) {
        reconnectTimerRef.current = setTimeout(() => {
          reconnectTimerRef.current = null
          console.log('[AgentActivity] 🔄 Reconnecting SSE stream...')
          connectStream().catch((err) => {
            console.error('[AgentActivity] Error reconnecting:', err)
          })
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
  }, [ingestBatch, reset, sessionId, token, refreshToken])
  
  // Reconnect when token changes
  useEffect(() => {
    if (token && eventSourceRef.current && eventSourceRef.current.readyState === EventSource.CLOSED) {
      console.log('[AgentActivity] Token updated, reconnecting SSE stream...')
      connectStream().catch((err) => {
        console.error('[AgentActivity] Error reconnecting after token update:', err)
      })
    }
  }, [token, connectStream])

  useEffect(() => {
    isUnmountedRef.current = false
    reset()
    connectStream().catch((err) => {
      console.error('[AgentActivity] Error connecting stream on mount:', err)
    })
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

      // First pass: find the most recent "completed" event
      let mostRecentCompleted: AgentActivityEvent | null = null
      for (let i = history.length - 1; i >= 0; i -= 1) {
        const evt = history[i]
        if (evt.status === 'completed') {
          mostRecentCompleted = evt
          break
        }
      }

      // Second pass: check for active states, but respect "completed" if it's more recent
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

        // If there's a "completed" event more recent than this "started" event, prioritize "completed"
        if (mostRecentCompleted && evt.status === 'started') {
          const completedTime = new Date(mostRecentCompleted.timestamp).getTime()
          if (completedTime > evtTime) {
            // "completed" is more recent, skip this "started" event
            continue
          }
        }

        // Prioritize active states (error, waiting, started) over completed
        // This ensures that if an agent is currently running, we show that state
        // even if there's a more recent "completed" event
        if (evt.status === 'error' && age <= ERROR_WINDOW_MS) {
          return summaryBase
        }
        if (evt.status === 'waiting' && age <= WAITING_WINDOW_MS) {
          return summaryBase
        }
        if (evt.status === 'started' && age <= ACTIVE_WINDOW_MS) {
          // If we find a "started" event within the active window, show it immediately
          // This ensures the agent appears as "in esecuzione" even if it completes quickly
          // BUT only if there's no more recent "completed" event
          if (!mostRecentCompleted || new Date(mostRecentCompleted.timestamp).getTime() <= evtTime) {
            return summaryBase
          }
        }
        // Store the most recent event as fallback (but prioritize active states above)
        if (!fallback) {
          fallback = summaryBase
        }
      }

      if (fallback && fallback.timestamp) {
        // Check if the fallback event is still recent enough to be shown
        const fallbackTime = new Date(fallback.timestamp).getTime()
        const fallbackAge = Number.isFinite(fallbackTime) ? now - fallbackTime : Number.POSITIVE_INFINITY
        
        // If there's a "completed" event more recent than the fallback, use that instead
        if (mostRecentCompleted) {
          const completedTime = new Date(mostRecentCompleted.timestamp).getTime()
          const completedAge = Number.isFinite(completedTime) ? now - completedTime : Number.POSITIVE_INFINITY
          
          // If "completed" is more recent than fallback, use "completed"
          if (completedTime > fallbackTime) {
            if (completedAge <= COMPLETED_WINDOW_MS) {
              return {
                agentId,
                agentName: mostRecentCompleted.agent_name || agentNameFallback,
                status: 'completed',
                message: mostRecentCompleted.message,
                timestamp: mostRecentCompleted.timestamp,
              }
            } else {
              // "completed" is too old, show as idle
              return {
                agentId,
                agentName: mostRecentCompleted.agent_name || agentNameFallback,
                status: 'idle',
              }
            }
          }
        }
        
        // IMPORTANT: Check for "started" events, but only if there's no more recent "completed"
        if (fallback.status === 'started' && fallbackAge <= ACTIVE_WINDOW_MS) {
          // Only show "started" if there's no more recent "completed"
          if (!mostRecentCompleted || new Date(mostRecentCompleted.timestamp).getTime() <= fallbackTime) {
            return fallback
          }
        }
        
        // For "completed" status, only show it if it's within the completed window
        // After COMPLETED_WINDOW_MS, transition to idle
        if (fallback.status === 'completed') {
          if (fallbackAge > COMPLETED_WINDOW_MS) {
            return {
              agentId,
              agentName: fallback.agentName,
              status: 'idle',
            }
          }
          // Still within window, show as completed
          return fallback
        }
        // For other statuses (waiting, error), only show if recent
        // If the event is too old, show as idle
        else if (fallback.status === 'waiting' && fallbackAge > WAITING_WINDOW_MS) {
          return {
            agentId,
            agentName: fallback.agentName,
            status: 'idle',
          }
        }
        else if (fallback.status === 'error' && fallbackAge > ERROR_WINDOW_MS) {
          return {
            agentId,
            agentName: fallback.agentName,
            status: 'idle',
          }
        }
        // If fallback is "started" but too old, check if there's a more recent "started" event
        else if (fallback.status === 'started' && fallbackAge > ACTIVE_WINDOW_MS) {
          // Look for a more recent "started" event in the history
          for (let j = history.length - 1; j >= 0; j -= 1) {
            const recentEvt = history[j]
            if (recentEvt.status === 'started') {
              const recentTime = new Date(recentEvt.timestamp).getTime()
              const recentAge = Number.isFinite(recentTime) ? now - recentTime : Number.POSITIVE_INFINITY
              if (recentAge <= ACTIVE_WINDOW_MS) {
                return {
                  agentId,
                  agentName: recentEvt.agent_name || fallback.agentName,
                  status: 'started',
                  message: recentEvt.message,
                  timestamp: recentEvt.timestamp,
                }
              }
            }
          }
          // No recent "started" event found, show as idle
          return {
            agentId,
            agentName: fallback.agentName,
            status: 'idle',
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


