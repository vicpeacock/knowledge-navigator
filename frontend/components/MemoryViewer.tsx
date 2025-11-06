'use client'

import { useState, useEffect } from 'react'
import { sessionsApi } from '@/lib/api'
import { Brain, X, Clock, Archive, FileText, MessageSquare } from 'lucide-react'
import { format } from 'date-fns'

interface LongTermMemoryItem {
  content: string
  importance_score: number
  created_at: string
  learned_from_sessions: string[]
}

interface MemoryInfo {
  short_term: {
    last_user_message?: string
    last_assistant_message?: string
    message_count?: number
  } | null
  medium_term_samples: string[]
  long_term_samples: string[]
  long_term_memories?: LongTermMemoryItem[]  // New: full details
  files_count: number
  total_messages: number
}

interface MemoryViewerProps {
  sessionId: string
  isOpen: boolean
  onClose: () => void
}

export default function MemoryViewer({ sessionId, isOpen, onClose }: MemoryViewerProps) {
  const [memoryInfo, setMemoryInfo] = useState<MemoryInfo | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (isOpen && sessionId) {
      loadMemoryInfo()
    }
  }, [isOpen, sessionId])

  const loadMemoryInfo = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await sessionsApi.getMemory(sessionId)
      setMemoryInfo(response.data)
    } catch (err: any) {
      console.error('Error loading memory info:', err)
      setError(err.response?.data?.detail || err.message || 'Errore nel caricamento della memoria')
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] p-6 flex flex-col">
        <div className="flex justify-between items-center border-b pb-3 mb-4">
          <div className="flex items-center gap-2">
            <Brain size={24} className="text-blue-600 dark:text-blue-400" />
            <h2 className="text-xl font-semibold">Memoria della Sessione</h2>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
          >
            <X size={24} />
          </button>
        </div>

        {loading ? (
          <div className="flex justify-center items-center h-48">
            <div className="flex gap-2">
              <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce"></div>
              <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
              <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
            </div>
          </div>
        ) : error ? (
          <div className="text-center py-8 text-red-600 dark:text-red-400">
            <p>{error}</p>
          </div>
        ) : memoryInfo ? (
          <div className="flex-1 overflow-y-auto space-y-6">
            {/* Statistics */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <MessageSquare size={20} className="text-blue-600 dark:text-blue-400" />
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Messaggi</span>
                </div>
                <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">{memoryInfo.total_messages}</p>
              </div>
              <div className="bg-green-50 dark:bg-green-900/20 p-4 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <FileText size={20} className="text-green-600 dark:text-green-400" />
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">File</span>
                </div>
                <p className="text-2xl font-bold text-green-600 dark:text-green-400">{memoryInfo.files_count}</p>
              </div>
              <div className="bg-yellow-50 dark:bg-yellow-900/20 p-4 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <Clock size={20} className="text-yellow-600 dark:text-yellow-400" />
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Medio termine</span>
                </div>
                <p className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">{memoryInfo.medium_term_samples.length}</p>
              </div>
              <div className="bg-purple-50 dark:bg-purple-900/20 p-4 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <Archive size={20} className="text-purple-600 dark:text-purple-400" />
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Lungo termine</span>
                </div>
                <p className="text-2xl font-bold text-purple-600 dark:text-purple-400">{memoryInfo.long_term_samples.length}</p>
              </div>
            </div>

            {/* Short-term Memory */}
            {memoryInfo.short_term && (
              <div className="bg-gray-50 dark:bg-gray-700/50 p-4 rounded-lg">
                <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
                  <Clock size={18} className="text-blue-600 dark:text-blue-400" />
                  Memoria a Breve Termine
                </h3>
                <div className="space-y-2 text-sm">
                  {memoryInfo.short_term.message_count && (
                    <p>
                      <span className="font-medium">Messaggi nella sessione:</span>{' '}
                      {memoryInfo.short_term.message_count}
                    </p>
                  )}
                  {memoryInfo.short_term.last_user_message && (
                    <div>
                      <p className="font-medium mb-1">Ultimo messaggio utente:</p>
                      <p className="bg-white dark:bg-gray-800 p-2 rounded text-gray-800 dark:text-gray-200">
                        {memoryInfo.short_term.last_user_message}
                      </p>
                    </div>
                  )}
                  {memoryInfo.short_term.last_assistant_message && (
                    <div>
                      <p className="font-medium mb-1">Ultima risposta assistente:</p>
                      <p className="bg-white dark:bg-gray-800 p-2 rounded text-gray-800 dark:text-gray-200">
                        {memoryInfo.short_term.last_assistant_message.substring(0, 200)}
                        {memoryInfo.short_term.last_assistant_message.length > 200 ? '...' : ''}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Medium-term Memory Samples */}
            {memoryInfo.medium_term_samples.length > 0 && (
              <div className="bg-gray-50 dark:bg-gray-700/50 p-4 rounded-lg">
                <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
                  <Clock size={18} className="text-yellow-600 dark:text-yellow-400" />
                  Memoria a Medio Termine (Esempi)
                </h3>
                <div className="space-y-3">
                  {memoryInfo.medium_term_samples.map((sample, index) => (
                    <div
                      key={index}
                      className="bg-white dark:bg-gray-800 p-3 rounded border-l-4 border-yellow-500"
                    >
                      <p className="text-sm text-gray-800 dark:text-gray-200">
                        {sample.length > 300 ? `${sample.substring(0, 300)}...` : sample}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Long-term Memory - Show full details if available, otherwise samples */}
            {(memoryInfo.long_term_memories && memoryInfo.long_term_memories.length > 0) || memoryInfo.long_term_samples.length > 0 ? (
              <div className="bg-gray-50 dark:bg-gray-700/50 p-4 rounded-lg">
                <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
                  <Archive size={18} className="text-purple-600 dark:text-purple-400" />
                  Memoria a Lungo Termine (Conoscenza Condivisa)
                  {memoryInfo.long_term_memories && (
                    <span className="text-sm font-normal text-gray-500 dark:text-gray-400">
                      ({memoryInfo.long_term_memories.length} memorie)
                    </span>
                  )}
                </h3>
                <div className="space-y-3">
                  {/* Show full details if available */}
                  {memoryInfo.long_term_memories && memoryInfo.long_term_memories.length > 0 ? (
                    memoryInfo.long_term_memories.map((memory, index) => (
                      <div
                        key={index}
                        className="bg-white dark:bg-gray-800 p-4 rounded border-l-4 border-purple-500"
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs font-semibold px-2 py-1 rounded bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300">
                              Importanza: {(memory.importance_score * 100).toFixed(0)}%
                            </span>
                            {memory.learned_from_sessions && memory.learned_from_sessions.length > 0 && (
                              <span className="text-xs text-gray-500 dark:text-gray-400">
                                Da {memory.learned_from_sessions.length} sessione{memory.learned_from_sessions.length > 1 ? 'i' : ''}
                              </span>
                            )}
                          </div>
                          <span className="text-xs text-gray-500 dark:text-gray-400">
                            {format(new Date(memory.created_at), 'dd/MM/yyyy HH:mm')}
                          </span>
                        </div>
                        <p className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap">
                          {memory.content.length > 500 ? (
                            <details>
                              <summary className="cursor-pointer text-purple-600 dark:text-purple-400 hover:underline mb-2">
                                {memory.content.substring(0, 200)}... (click per espandere)
                              </summary>
                              <div className="mt-2">
                                {memory.content}
                              </div>
                            </details>
                          ) : (
                            memory.content
                          )}
                        </p>
                      </div>
                    ))
                  ) : (
                    // Fallback to samples if full details not available
                    memoryInfo.long_term_samples.map((sample, index) => (
                      <div
                        key={index}
                        className="bg-white dark:bg-gray-800 p-3 rounded border-l-4 border-purple-500"
                      >
                        <p className="text-sm text-gray-800 dark:text-gray-200">
                          {sample.length > 300 ? `${sample.substring(0, 300)}...` : sample}
                        </p>
                      </div>
                    ))
                  )}
                </div>
              </div>
            ) : null}

            {!memoryInfo.short_term && 
             memoryInfo.medium_term_samples.length === 0 && 
             memoryInfo.long_term_samples.length === 0 &&
             memoryInfo.files_count === 0 &&
             memoryInfo.total_messages === 0 && (
              <div className="text-center py-8 text-gray-500">
                <Brain size={48} className="mx-auto mb-4 opacity-50" />
                <p>Nessuna memoria disponibile per questa sessione.</p>
              </div>
            )}
            
            {/* Show message if there's data but no structured memory */}
            {(!memoryInfo.short_term && 
              memoryInfo.medium_term_samples.length === 0 && 
              memoryInfo.long_term_samples.length === 0) &&
             (memoryInfo.files_count > 0 || memoryInfo.total_messages > 0) && (
              <div className="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg border border-blue-200 dark:border-blue-800">
                <p className="text-sm text-blue-800 dark:text-blue-200">
                  <strong>Nota:</strong> La sessione contiene {memoryInfo.total_messages} messaggi e {memoryInfo.files_count} file, 
                  ma non è ancora stata creata memoria strutturata a medio o lungo termine. 
                  La memoria strutturata viene creata automaticamente durante le conversazioni.
                </p>
              </div>
            )}
          </div>
        ) : null}

        <div className="mt-4 pt-4 border-t flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-200 dark:bg-gray-600 text-gray-800 dark:text-white rounded-lg hover:bg-gray-300 dark:hover:bg-gray-700"
          >
            Chiudi
          </button>
        </div>
      </div>
    </div>
  )
}

