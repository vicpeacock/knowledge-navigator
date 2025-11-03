'use client'

import { useState } from 'react'
import { memoryApi } from '@/lib/api'

export default function MemoryView() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [memoryType, setMemoryType] = useState<'long' | 'medium'>('long')

  const handleSearch = async () => {
    if (!query.trim()) return

    setLoading(true)
    try {
      let response
      if (memoryType === 'long') {
        response = await memoryApi.getLongTerm(query, 10)
      } else {
        // For medium-term, we'd need a session ID - placeholder for now
        response = await memoryApi.getLongTerm(query, 10)
      }
      setResults(response.data.results || [])
    } catch (error) {
      console.error('Error searching memory:', error)
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6 bg-white dark:bg-gray-800 rounded-lg shadow">
      <h2 className="text-2xl font-semibold mb-4">Long-term Memory Search</h2>
      
      <div className="flex gap-2 mb-4">
        <select
          value={memoryType}
          onChange={(e) => setMemoryType(e.target.value as 'long' | 'medium')}
          className="p-2 border rounded"
        >
          <option value="long">Long-term</option>
          <option value="medium">Medium-term</option>
        </select>
        
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
          placeholder="Search memory..."
          className="flex-1 p-2 border rounded"
        />
        
        <button
          onClick={handleSearch}
          disabled={loading || !query.trim()}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Searching...' : 'Search'}
        </button>
      </div>

      <div className="space-y-2">
        {results.map((result, index) => (
          <div
            key={index}
            className="p-3 bg-gray-100 dark:bg-gray-700 rounded text-sm"
          >
            {result}
          </div>
        ))}
        
        {results.length === 0 && !loading && query && (
          <p className="text-gray-500 text-sm">No results found</p>
        )}
      </div>
    </div>
  )
}

