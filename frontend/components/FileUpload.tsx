'use client'

import { useState } from 'react'
import { filesApi } from '@/lib/api'

interface FileUploadProps {
  sessionId?: string  // Optional: for backward compatibility
  onUploaded?: () => void
}

export default function FileUpload({ sessionId, onUploaded }: FileUploadProps) {
  const [uploading, setUploading] = useState(false)

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    try {
      // Files are now user-scoped, sessionId is optional
      await filesApi.upload(file, sessionId)
      alert('File caricato con successo!')
      if (onUploaded) {
        onUploaded()
      }
    } catch (error) {
      console.error('Error uploading file:', error)
      alert('Errore nel caricamento del file')
    } finally {
      setUploading(false)
      e.target.value = '' // Reset input
    }
  }

  return (
    <label className="cursor-pointer">
      <input
        type="file"
        onChange={handleFileSelect}
        disabled={uploading}
        className="hidden"
      />
      <span className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 text-sm">
        {uploading ? 'Uploading...' : 'Upload File'}
      </span>
    </label>
  )
}

