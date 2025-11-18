'use client'

import MemoryView from '@/components/MemoryView'
import LongTermMemoryManager from '@/components/LongTermMemoryManager'
import { useState } from 'react'

export default function MemoryPage() {
  const [activeTab, setActiveTab] = useState<'search' | 'manage'>('manage')

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-6xl mx-auto">
        <div className="mb-6">
          <div className="flex gap-2 border-b">
            <button
              onClick={() => setActiveTab('manage')}
              className={`px-4 py-2 font-medium ${
                activeTab === 'manage'
                  ? 'border-b-2 border-blue-600 text-blue-600'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              }`}
            >
              Gestione Memoria
            </button>
            <button
              onClick={() => setActiveTab('search')}
              className={`px-4 py-2 font-medium ${
                activeTab === 'search'
                  ? 'border-b-2 border-blue-600 text-blue-600'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              }`}
            >
              Ricerca Memoria
            </button>
          </div>
        </div>
        {activeTab === 'manage' ? <LongTermMemoryManager /> : <MemoryView />}
      </div>
    </div>
  )
}

