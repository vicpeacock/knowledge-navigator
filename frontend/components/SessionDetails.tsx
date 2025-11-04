'use client'

import { useState } from 'react'
import Link from 'next/link'
import { sessionsApi } from '@/lib/api'
import { Session } from '@/types'
import { Edit2, X, Save, Archive, Trash2, RotateCcw, Home } from 'lucide-react'

interface SessionDetailsProps {
  session: Session
  onUpdate: () => void
}

export default function SessionDetails({ session, onUpdate }: SessionDetailsProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [title, setTitle] = useState(session.title || '')
  const [description, setDescription] = useState(session.description || '')
  const [loading, setLoading] = useState(false)

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
      <div className="mb-3">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors text-sm"
        >
          <Home size={16} />
          <span>Home</span>
        </Link>
      </div>
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

