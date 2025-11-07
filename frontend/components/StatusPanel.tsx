'use client'

import { useState, createContext, useContext, ReactNode } from 'react'
import { CheckCircle, XCircle, MessageSquare, ChevronUp, ChevronDown, X } from 'lucide-react'

export interface StatusMessage {
  id: string
  type: 'success' | 'error' | 'info' | 'warning'
  message: string
  timestamp: Date
}

interface StatusContextType {
  addStatusMessage: (type: 'success' | 'error' | 'info' | 'warning', message: string) => void
  removeStatusMessage: (id: string) => void
  clearAllStatusMessages: () => void
  statusMessages: StatusMessage[]
}

const StatusContext = createContext<StatusContextType | undefined>(undefined)

export function StatusProvider({ children }: { children: ReactNode }) {
  const [statusMessages, setStatusMessages] = useState<StatusMessage[]>([])
  const [statusPanelExpanded, setStatusPanelExpanded] = useState(false)

  const addStatusMessage = (type: 'success' | 'error' | 'info' | 'warning', message: string) => {
    const id = Date.now().toString() + Math.random().toString(36).substr(2, 9)
    const newMessage: StatusMessage = { id, type, message, timestamp: new Date() }
    setStatusMessages(prev => [...prev, newMessage].slice(-50)) // Keep last 50 messages (increased from 20)
    // Auto-expand panel when new message arrives
    if (!statusPanelExpanded) {
      setStatusPanelExpanded(true)
    }
    // Messages are now persistent - user must manually remove them
    // No auto-removal to prevent important notifications from disappearing
  }

  const removeStatusMessage = (id: string) => {
    setStatusMessages(prev => prev.filter(m => m.id !== id))
  }

  const clearAllStatusMessages = () => {
    setStatusMessages([])
  }

  return (
    <StatusContext.Provider value={{ addStatusMessage, removeStatusMessage, clearAllStatusMessages, statusMessages }}>
      {children}
      
      {/* Status Messages Panel - Collapsible, positioned at bottom */}
      <div className={`fixed bottom-0 left-0 right-0 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 shadow-lg transition-all duration-300 z-50 ${
        statusPanelExpanded ? 'h-96' : 'h-12'
      }`}>
        <div 
          className="flex items-center justify-between p-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700"
          onClick={() => setStatusPanelExpanded(!statusPanelExpanded)}
        >
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm text-gray-700 dark:text-gray-300">
              Status Updates
            </span>
            {statusMessages.length > 0 && (
              <span className="px-2 py-0.5 bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded-full text-xs font-medium">
                {statusMessages.length}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {statusMessages.length > 0 && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  clearAllStatusMessages()
                }}
                className="p-1 hover:bg-gray-200 dark:hover:bg-gray-600 rounded"
                title="Clear all"
              >
                <X size={16} className="text-gray-500 dark:text-gray-400" />
              </button>
            )}
            {statusPanelExpanded ? (
              <ChevronDown size={20} className="text-gray-500 dark:text-gray-400" />
            ) : (
              <ChevronUp size={20} className="text-gray-500 dark:text-gray-400" />
            )}
          </div>
        </div>
        
        {statusPanelExpanded && (
          <div className="h-[calc(100%-3rem)] overflow-y-auto p-3 space-y-2">
            {statusMessages.length === 0 ? (
              <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-4">
                Nessun messaggio di stato
              </p>
            ) : (
              statusMessages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex items-start gap-2 p-2 rounded-lg text-sm ${
                    msg.type === 'success' 
                      ? 'bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-200 border border-green-200 dark:border-green-800'
                      : msg.type === 'error'
                      ? 'bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200 border border-red-200 dark:border-red-800'
                      : msg.type === 'warning'
                      ? 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-800 dark:text-yellow-200 border border-yellow-200 dark:border-yellow-800'
                      : 'bg-blue-50 dark:bg-blue-900/20 text-blue-800 dark:text-blue-200 border border-blue-200 dark:border-blue-800'
                  }`}
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      {msg.type === 'success' && <CheckCircle size={16} />}
                      {msg.type === 'error' && <XCircle size={16} />}
                      {msg.type === 'warning' && <XCircle size={16} />}
                      {msg.type === 'info' && <MessageSquare size={16} />}
                      <span className="font-medium capitalize">{msg.type}</span>
                      <span className="text-xs text-gray-500 dark:text-gray-400 ml-auto">
                        {msg.timestamp.toLocaleTimeString()}
                      </span>
                    </div>
                    <p className="text-xs whitespace-pre-wrap">{msg.message}</p>
                  </div>
                  <button
                    onClick={() => removeStatusMessage(msg.id)}
                    className="p-1 hover:bg-black/10 dark:hover:bg-white/10 rounded"
                    title="Remove"
                  >
                    <X size={14} />
                  </button>
                </div>
              )).reverse()
            )}
          </div>
        )}
      </div>
    </StatusContext.Provider>
  )
}

export function useStatus() {
  const context = useContext(StatusContext)
  if (context === undefined) {
    throw new Error('useStatus must be used within a StatusProvider')
  }
  return context
}

