'use client'

import { useState, useEffect } from 'react'
import { memoryApi } from '@/lib/api'
import { Brain, Trash2, CheckSquare, Square, Loader2, AlertCircle } from 'lucide-react'
import { format } from 'date-fns'

interface LongTermMemoryItem {
  id: string
  content: string
  importance_score: number
  learned_from_sessions: string[]
  created_at: string | null
  embedding_id: string | null
}

interface LongTermMemoryListResponse {
  items: LongTermMemoryItem[]
  total: number
  limit: number
  offset: number
}

export default function LongTermMemoryManager() {
  const [memories, setMemories] = useState<LongTermMemoryItem[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [total, setTotal] = useState(0)
  const [limit] = useState(100)
  const [offset, setOffset] = useState(0)

  useEffect(() => {
    loadMemories()
  }, [offset])

  const loadMemories = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await memoryApi.listLongTerm(limit, offset)
      const data: LongTermMemoryListResponse = response.data
      setMemories(data.items)
      setTotal(data.total)
    } catch (err: any) {
      console.error('Error loading long-term memories:', err)
      setError(err.response?.data?.detail || err.message || 'Errore nel caricamento delle memorie')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectAll = () => {
    if (selectedIds.size === memories.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(memories.map(m => m.id)))
    }
  }

  const handleSelectItem = (id: string) => {
    const newSelected = new Set(selectedIds)
    if (newSelected.has(id)) {
      newSelected.delete(id)
    } else {
      newSelected.add(id)
    }
    setSelectedIds(newSelected)
  }

  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) {
      return
    }

    if (!confirm(`Vuoi eliminare ${selectedIds.size} memorie selezionate?`)) {
      return
    }

    setDeleting(true)
    setError(null)
    try {
      await memoryApi.deleteLongTermBatch(Array.from(selectedIds))
      setSelectedIds(new Set())
      await loadMemories()
    } catch (err: any) {
      console.error('Error deleting memories:', err)
      setError(err.response?.data?.detail || err.message || 'Errore nella cancellazione delle memorie')
    } finally {
      setDeleting(false)
    }
  }

  const handleDeleteSingle = async (id: string) => {
    if (!confirm('Vuoi eliminare questa memoria?')) {
      return
    }

    setDeleting(true)
    setError(null)
    try {
      await memoryApi.deleteLongTermBatch([id])
      await loadMemories()
    } catch (err: any) {
      console.error('Error deleting memory:', err)
      setError(err.response?.data?.detail || err.message || 'Errore nella cancellazione della memoria')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="p-6 bg-white dark:bg-gray-800 rounded-lg shadow-lg">
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center gap-2">
          <Brain size={24} className="text-purple-600 dark:text-purple-400" />
          <h2 className="text-2xl font-semibold">Gestione Memoria a Lungo Termine</h2>
        </div>
        {selectedIds.size > 0 && (
          <button
            onClick={handleDeleteSelected}
            disabled={deleting}
            className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50 flex items-center gap-2"
          >
            {deleting ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Eliminazione...
              </>
            ) : (
              <>
                <Trash2 size={16} />
                Elimina Selezionate ({selectedIds.size})
              </>
            )}
          </button>
        )}
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-center gap-2">
          <AlertCircle size={20} className="text-red-600 dark:text-red-400" />
          <span className="text-red-800 dark:text-red-200">{error}</span>
        </div>
      )}

      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            onClick={handleSelectAll}
            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
            title="Seleziona/Deseleziona Tutto"
          >
            {selectedIds.size === memories.length && memories.length > 0 ? (
              <CheckSquare size={20} className="text-blue-600 dark:text-blue-400" />
            ) : (
              <Square size={20} className="text-gray-400" />
            )}
          </button>
          <span className="text-sm text-gray-600 dark:text-gray-400">
            {total} memorie totali
          </span>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setOffset(Math.max(0, offset - limit))}
            disabled={offset === 0 || loading}
            className="px-3 py-1 text-sm border rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50"
          >
            Precedente
          </button>
          <button
            onClick={() => setOffset(offset + limit)}
            disabled={offset + limit >= total || loading}
            className="px-3 py-1 text-sm border rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50"
          >
            Successivo
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 size={32} className="animate-spin text-blue-600 dark:text-blue-400" />
        </div>
      ) : memories.length === 0 ? (
        <div className="text-center py-12 text-gray-500 dark:text-gray-400">
          Nessuna memoria a lungo termine trovata
        </div>
      ) : (
        <div className="space-y-3">
          {memories.map((memory) => (
            <div
              key={memory.id}
              className="p-4 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700/50 flex items-start gap-3"
            >
              <button
                onClick={() => handleSelectItem(memory.id)}
                className="mt-1 p-1 hover:bg-gray-200 dark:hover:bg-gray-600 rounded"
              >
                {selectedIds.has(memory.id) ? (
                  <CheckSquare size={20} className="text-blue-600 dark:text-blue-400" />
                ) : (
                  <Square size={20} className="text-gray-400" />
                )}
              </button>
              <div className="flex-1">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <p className="text-sm text-gray-900 dark:text-gray-100 mb-2">
                      {memory.content}
                    </p>
                    <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
                      <span>
                        Importanza: {memory.importance_score.toFixed(2)}
                      </span>
                      {memory.created_at && (
                        <span>
                          {format(new Date(memory.created_at), 'dd/MM/yyyy HH:mm')}
                        </span>
                      )}
                      {memory.learned_from_sessions.length > 0 && (
                        <span>
                          Da {memory.learned_from_sessions.length} sessione/i
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => handleDeleteSingle(memory.id)}
                    disabled={deleting}
                    className="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded disabled:opacity-50"
                    title="Elimina"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

