'use client'

import { useState, useEffect } from 'react'
import { filesApi } from '@/lib/api'
import { File as FileType } from '@/types'
import { Trash2, FileIcon, X } from 'lucide-react'
import { format } from 'date-fns'

interface FileManagerProps {
  sessionId?: string  // Optional: for backward compatibility
  isOpen: boolean
  onClose: () => void
  onFileUploaded?: () => void
}

export default function FileManager({ sessionId, isOpen, onClose, onFileUploaded }: FileManagerProps) {
  const [files, setFiles] = useState<FileType[]>([])
  const [loading, setLoading] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)

  useEffect(() => {
    if (isOpen) {
      console.log('[FileManager] Loading user files')
      loadFiles()
    }
  }, [isOpen])

  const loadFiles = async () => {
    setLoading(true)
    try {
      console.log('[FileManager] Calling filesApi.list (user-scoped)')
      const response = await filesApi.list()  // Files are now user-scoped
      console.log('[FileManager] Files loaded:', response.data)
      setFiles(response.data || [])
    } catch (error: any) {
      console.error('[FileManager] Error loading files:', error)
      const errorMessage = error.response?.data?.detail || error.message || 'Errore nel caricamento dei file'
      alert(`Error loading files: ${errorMessage}`)
      setFiles([])
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (fileId: string, filename: string) => {
    if (!confirm(`Sei sicuro di voler eliminare "${filename}" dalla memoria dell'assistente?`)) {
      return
    }

    setDeleting(fileId)
    try {
      await filesApi.delete(fileId)
      await loadFiles()
      if (onFileUploaded) {
        onFileUploaded()
      }
    } catch (error) {
      console.error('Error deleting file:', error)
      alert('Error deleting file')
    } finally {
      setDeleting(null)
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
  }

  // Always render when isOpen is true
  if (!isOpen) {
    return null
  }

  console.log('[FileManager] Rendering popup - isOpen:', isOpen, 'sessionId:', sessionId, 'loading:', loading)

  return (
    <div 
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center"
      style={{ zIndex: 9999 }}
      onClick={(e) => {
        e.preventDefault()
        e.stopPropagation()
        if (e.target === e.currentTarget) {
          console.log('[FileManager] Backdrop clicked, closing')
          onClose()
        }
      }}
    >
      <div 
        className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-xl font-semibold">File in Memoria</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <div className="flex justify-center items-center py-8">
              <div className="flex gap-2">
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
              </div>
            </div>
          ) : files.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <FileIcon size={48} className="mx-auto mb-4 opacity-50" />
              <p>Nessun file caricato in questa sessione</p>
            </div>
          ) : (
            <div className="space-y-3">
              {files.map((file) => (
                <div
                  key={file.id}
                  className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors"
                >
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <FileIcon size={20} className="text-gray-500 dark:text-gray-400 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate">{file.filename}</p>
                      <div className="flex gap-3 text-xs text-gray-500 dark:text-gray-400">
                        <span>
                          {format(new Date(file.uploaded_at), 'dd/MM/yyyy HH:mm')}
                        </span>
                        {file.metadata?.file_size && (
                          <span>{formatFileSize(file.metadata.file_size)}</span>
                        )}
                        {file.mime_type && (
                          <span className="capitalize">{file.mime_type.split('/')[1]}</span>
                        )}
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(file.id, file.filename)}
                    disabled={deleting === file.id}
                    className="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors disabled:opacity-50"
                    title="Elimina dalla memoria"
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="p-4 border-t bg-gray-50 dark:bg-gray-700/50">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            {files.length} file{files.length !== 1 ? 's' : ''} in memoria
          </p>
        </div>
      </div>
    </div>
  )
}

