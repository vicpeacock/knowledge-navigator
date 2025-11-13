'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { sessionsApi } from '@/lib/api'
import { Session } from '@/types'
import clsx from 'clsx'
import {
  Edit2,
  X,
  Save,
  Archive,
  Trash2,
  RotateCcw,
  Home,
  Network,
  Workflow,
  Activity,
  Bot,
  Brain,
  ShieldCheck,
  BellRing,
  MessageSquare,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useAgentActivity } from './AgentActivityContext'
import NotificationBell from './NotificationBell'

interface SessionDetailsProps {
  session: Session
  onUpdate: () => void
}

export default function SessionDetails({ session, onUpdate }: SessionDetailsProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [title, setTitle] = useState(session.title || '')
  const [description, setDescription] = useState(session.description || '')
  const [loading, setLoading] = useState(false)
  const [showAgentActivity, setShowAgentActivity] = useState(false)

  const { agentStatuses, events, connectionState } = useAgentActivity()

  const agentDefinitions = useMemo(
    () =>
      new Map<string, { label: string; icon: LucideIcon }>([
        ['event_handler', { label: 'Event Handler', icon: Workflow }],
        ['orchestrator', { label: 'Orchestrator', icon: Activity }],
        ['planner', { label: 'Planner', icon: Bot }],
        ['tool_loop', { label: 'Tool Loop', icon: Network }],
        ['knowledge_agent', { label: 'Knowledge', icon: Brain }],
        ['background_integrity_agent', { label: 'Integrity', icon: ShieldCheck }],
        ['notification_collector', { label: 'Notifications', icon: BellRing }],
        ['response_formatter', { label: 'Response', icon: MessageSquare }],
      ]),
    []
  )

  const statusColorMap: Record<string, string> = {
    started: 'bg-emerald-500 text-white ring-2 ring-emerald-200 dark:ring-emerald-600/50',
    waiting: 'bg-amber-500 text-white ring-2 ring-amber-200 dark:ring-amber-600/50',
    error: 'bg-rose-500 text-white ring-2 ring-rose-200 dark:ring-rose-600/50',
    completed: 'bg-blue-200 text-blue-800 dark:bg-blue-900/60 dark:text-blue-200',
    idle: 'bg-slate-200 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
  }

  const statusLabelMap: Record<string, string> = {
    started: 'In esecuzione',
    waiting: 'In attesa',
    error: 'Errore',
    completed: 'Completato',
    idle: 'Idle',
  }

  const connectionBadge = useMemo(() => {
    const color =
      connectionState === 'open'
        ? 'bg-emerald-500'
        : connectionState === 'connecting'
        ? 'bg-amber-500'
        : 'bg-rose-500'
    const label =
      connectionState === 'open'
        ? 'Streaming attivo'
        : connectionState === 'connecting'
        ? 'Connessione...'
        : 'Streaming non disponibile'
    return { color, label }
  }, [connectionState])

  const latestEvents = useMemo(() => {
    return [...events]
      .slice(-12)
      .reverse()
      .map((evt) => ({
        key: `${evt.timestamp}|${evt.agent_id}|${evt.status}`,
        time: new Date(evt.timestamp).toLocaleTimeString(),
        agent: evt.agent_name,
        status: statusLabelMap[evt.status] ?? evt.status,
        message: evt.message,
      }))
  }, [events, statusLabelMap])

  const renderAgentStatus = (agentId: string, status: typeof agentStatuses[number]) => {
    const definition = agentDefinitions.get(agentId)
    const Icon = definition?.icon ?? Activity
    const bubbleClasses = clsx(
      'flex h-12 w-12 items-center justify-center rounded-full text-sm transition-colors',
      statusColorMap[status.status] ?? statusColorMap.idle
    )
    const label = definition?.label ?? status.agentName ?? agentId
    const statusLabel = statusLabelMap[status.status] ?? status.status
    
    // Get last 5 events for this agent
    const agentEvents = events
      .filter((e) => e.agent_id === agentId)
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
      .slice(0, 5)
    
    return (
      <div key={agentId} className="flex flex-col items-center gap-2 text-center text-xs text-blue-900 dark:text-blue-200 relative group">
        <span className={bubbleClasses}>
          <Icon size={18} />
        </span>
        <span className="font-medium leading-tight">{label}</span>
        <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">{statusLabel}</span>
        {status.timestamp && (
          <span className="text-[10px] text-slate-400 dark:text-slate-500">
            {new Date(status.timestamp).toLocaleTimeString()}
          </span>
        )}
        {status.message && <span className="text-[10px] text-slate-600 dark:text-slate-400">{status.message}</span>}
        
        {/* Tooltip with agent logs */}
        <div className="absolute top-full left-1/2 transform -translate-x-1/2 mt-2 w-64 p-3 bg-gray-900 dark:bg-gray-800 text-white text-xs rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50 pointer-events-none">
          <div className="font-semibold mb-2 text-sm border-b border-gray-700 pb-1">
            {label} - Ultimi eventi
          </div>
          {agentEvents.length > 0 ? (
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {agentEvents.map((event, idx) => (
                <div key={idx} className="text-left">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={clsx(
                      'px-1.5 py-0.5 rounded text-[10px] font-semibold',
                      event.status === 'started' && 'bg-emerald-600',
                      event.status === 'completed' && 'bg-blue-600',
                      event.status === 'waiting' && 'bg-amber-600',
                      event.status === 'error' && 'bg-rose-600'
                    )}>
                      {statusLabelMap[event.status] || event.status}
                    </span>
                    <span className="text-[10px] text-gray-400">
                      {new Date(event.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  {event.message && (
                    <div className="text-[11px] text-gray-300 ml-1">
                      {event.message}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-gray-400 text-[11px]">Nessun evento recente</div>
          )}
        </div>
      </div>
    )
  }

  const handleSave = async () => {
    setLoading(true)
    try {
      await sessionsApi.update(session.id, { title, description })
      setIsEditing(false)
      onUpdate()
    } catch (error: any) {
      console.error('Error updating session:', error)
      alert(`Error updating session: ${error.response?.data?.detail || error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleArchive = async () => {
    if (!confirm('Are you sure you want to archive this session?')) return
    setLoading(true)
    try {
      await sessionsApi.archive(session.id)
      onUpdate()
    } catch (error: any) {
      console.error('Error archiving session:', error)
      alert(`Error archiving session: ${error.response?.data?.detail || error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleRestore = async () => {
    setLoading(true)
    try {
      await sessionsApi.restore(session.id)
      onUpdate()
    } catch (error: any) {
      console.error('Error restoring session:', error)
      alert(`Error restoring session: ${error.response?.data?.detail || error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this session? This action cannot be undone.')) return
    setLoading(true)
    try {
      await sessionsApi.delete(session.id)
      window.location.href = '/'
    } catch (error: any) {
      console.error('Error deleting session:', error)
      alert(`Error deleting session: ${error.response?.data?.detail || error.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-white dark:bg-gray-800 p-4 border-b border-gray-200 dark:border-gray-700">
      <div className="mb-3 flex items-center gap-3">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors text-sm"
        >
          <Home size={16} />
          <span>Home</span>
        </Link>
        <NotificationBell sessionId={session.id} />
        <button
          type="button"
          onClick={() => setShowAgentActivity((prev) => !prev)}
          className="ml-auto inline-flex h-8 w-8 items-center justify-center rounded-full border border-gray-200 text-gray-600 transition-colors hover:bg-blue-50 hover:text-blue-600 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-700 dark:hover:text-blue-300"
          title={showAgentActivity ? 'Nascondi attività agenti' : 'Mostra attività agenti'}
        >
          <Network size={18} />
        </button>
      </div>
      {showAgentActivity && (
        <div className="mb-4 rounded-lg border border-blue-100 bg-blue-50/70 p-4 shadow-sm dark:border-blue-900/40 dark:bg-blue-950/20">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-blue-900 dark:text-blue-200">Agent Activity</h3>
            <span className="flex items-center gap-2 text-xs font-medium text-slate-600 dark:text-slate-300">
              <span className={clsx('h-2.5 w-2.5 rounded-full', connectionBadge.color)} />
              {connectionBadge.label}
            </span>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-8">
            {agentStatuses.map((status) => renderAgentStatus(status.agentId, status))}
          </div>
          <div className="mt-4">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-blue-900 dark:text-blue-200">
              Ultimi eventi
            </h4>
            <div className="mt-2 max-h-36 overflow-y-auto rounded-lg border border-blue-100 bg-white/70 p-2 text-xs shadow-inner dark:border-blue-900/40 dark:bg-slate-900/60">
              {latestEvents.length === 0 ? (
                <p className="text-[11px] text-slate-500 dark:text-slate-400">In attesa di telemetria dagli agenti…</p>
              ) : (
                <ul className="space-y-1.5">
                  {latestEvents.map((evt) => (
                    <li key={evt.key} className="flex items-start gap-2 text-slate-700 dark:text-slate-200">
                      <span className="font-mono text-[10px] text-slate-500 dark:text-slate-400">{evt.time}</span>
                      <span className="font-semibold">{evt.agent}</span>
                      <span className="text-[11px] text-slate-500 dark:text-slate-400">{evt.status}</span>
                      {evt.message && <span className="text-[11px] text-slate-600 dark:text-slate-300">— {evt.message}</span>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
      {isEditing ? (
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium mb-1">Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white"
              placeholder="Session title"
              maxLength={255}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white"
              placeholder="Session description"
              rows={3}
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleSave}
              disabled={loading}
              className="px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 flex items-center gap-1 text-sm"
            >
              <Save size={14} />
              Save
            </button>
            <button
              onClick={() => {
                setIsEditing(false)
                setTitle(session.title || '')
                setDescription(session.description || '')
              }}
              disabled={loading}
              className="px-3 py-1.5 bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-white rounded hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50 flex items-center gap-1 text-sm"
            >
              <X size={14} />
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <h2 className="text-xl font-semibold">{session.title || session.name}</h2>
              {session.description && (
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">{session.description}</p>
              )}
              {!session.title && !session.description && (
                <p className="text-sm text-gray-500 dark:text-gray-500 italic">No title or description</p>
              )}
            </div>
            <button
              onClick={() => setIsEditing(true)}
              className="p-1.5 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
              title="Edit session"
            >
              <Edit2 size={18} />
            </button>
          </div>
          <div className="flex gap-2 flex-wrap">
            {session.status === 'active' && (
              <>
                <button
                  onClick={handleArchive}
                  disabled={loading}
                  className="px-3 py-1.5 bg-yellow-600 text-white rounded hover:bg-yellow-700 disabled:opacity-50 flex items-center gap-1 text-sm"
                  title="Archive session"
                >
                  <Archive size={14} />
                  Archive
                </button>
                <button
                  onClick={handleDelete}
                  disabled={loading}
                  className="px-3 py-1.5 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50 flex items-center gap-1 text-sm"
                  title="Delete session"
                >
                  <Trash2 size={14} />
                  Delete
                </button>
              </>
            )}
            {session.status === 'archived' && (
              <button
                onClick={handleRestore}
                disabled={loading}
                className="px-3 py-1.5 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50 flex items-center gap-1 text-sm"
                title="Restore session"
              >
                <RotateCcw size={14} />
                Restore
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

