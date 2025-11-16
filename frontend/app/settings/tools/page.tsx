'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { usersApi } from '@/lib/api'
import ProtectedRoute from '@/components/ProtectedRoute'

interface Tool {
  name: string
  description?: string
  parameters?: any
  mcp_integration_id?: string
  mcp_tool_name?: string
}

interface ToolsPreferencesData {
  available_tools: Tool[]
  user_preferences: string[]
}

function ToolsPreferencesContent() {
  const router = useRouter()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [toolsData, setToolsData] = useState<ToolsPreferencesData | null>(null)
  const [selectedTools, setSelectedTools] = useState<Set<string>>(new Set())
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  useEffect(() => {
    loadToolsPreferences()
  }, [])

  const loadToolsPreferences = async () => {
    try {
      setLoading(true)
      setError(null)
      console.log('Loading tools preferences...')
      const response = await usersApi.getToolsPreferences()
      console.log('Tools preferences response:', response)
      const data = response.data as ToolsPreferencesData
      console.log('Tools data:', data)
      if (!data || !data.available_tools) {
        throw new Error('Invalid response format')
      }
      setToolsData(data)
      setSelectedTools(new Set(data.user_preferences))
      console.log('Tools preferences loaded successfully')
    } catch (err: any) {
      console.error('Error loading tools preferences:', err)
      console.error('Error details:', {
        message: err.message,
        response: err.response,
        data: err.response?.data,
      })
      setError(
        err.response?.data?.detail || 
        err.message || 
        'Failed to load tools preferences. Please check the console for details.'
      )
    } finally {
      setLoading(false)
    }
  }

  const handleToolToggle = (toolName: string) => {
    const newSelected = new Set(selectedTools)
    if (newSelected.has(toolName)) {
      newSelected.delete(toolName)
    } else {
      newSelected.add(toolName)
    }
    setSelectedTools(newSelected)
  }

  const handleSelectAll = () => {
    if (!toolsData || !toolsData.available_tools) return
    const availableTools = toolsData.available_tools || []
    if (selectedTools.size === availableTools.length) {
      setSelectedTools(new Set())
    } else {
      setSelectedTools(new Set(availableTools.map(t => t.name)))
    }
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      setError(null)
      setSuccess(null)
      
      await usersApi.updateToolsPreferences(Array.from(selectedTools))
      
      setSuccess('Tools preferences updated successfully!')
      
      // Reload to get updated data
      await loadToolsPreferences()
    } catch (err: any) {
      console.error('Error saving tools preferences:', err)
      setError(err.response?.data?.detail || 'Failed to save tools preferences')
    } finally {
      setSaving(false)
    }
  }

  const groupToolsByType = (tools: Tool[] | undefined) => {
    const baseTools: Tool[] = []
    const mcpTools: Tool[] = []
    
    if (!tools || !Array.isArray(tools)) {
      return { baseTools, mcpTools }
    }
    
    tools.forEach(tool => {
      if (tool && tool.name && tool.name.startsWith('mcp_')) {
        mcpTools.push(tool)
      } else if (tool && tool.name) {
        baseTools.push(tool)
      }
    })
    
    return { baseTools, mcpTools }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-4xl mx-auto">
          <div className="bg-white rounded-lg shadow p-6">
            <p className="text-gray-600">Loading tools preferences...</p>
          </div>
        </div>
      </div>
    )
  }

  if (!toolsData) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-4xl mx-auto">
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Tools Preferences</h2>
            {error ? (
              <div>
                <p className="text-red-600 mb-4">{error}</p>
                <button
                  onClick={loadToolsPreferences}
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                  Retry
                </button>
              </div>
            ) : (
              <p className="text-gray-600">Loading tools preferences...</p>
            )}
          </div>
        </div>
      </div>
    )
  }

  const availableTools = toolsData.available_tools || []
  const { baseTools, mcpTools } = groupToolsByType(availableTools)
  const allSelected = availableTools.length > 0 && selectedTools.size === availableTools.length
  const someSelected = selectedTools.size > 0 && selectedTools.size < availableTools.length

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Tools Preferences</h1>
              <p className="mt-2 text-gray-600">
                Select which tools you want to enable for your AI assistant
              </p>
            </div>
            <a
              href="/"
              className="px-4 py-2 text-gray-700 hover:text-gray-900 underline"
            >
              Home
            </a>
          </div>
        </div>

        {/* Messages */}
        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
            {error}
          </div>
        )}
        {success && (
          <div className="mb-4 bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded">
            {success}
          </div>
        )}

        {/* Tools List */}
        <div className="bg-white rounded-lg shadow">
          {/* Header with Select All */}
          <div className="border-b border-gray-200 px-6 py-4 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Available Tools</h2>
              <p className="text-sm text-gray-600 mt-1">
                {selectedTools.size} of {availableTools.length} tools selected
              </p>
            </div>
            <button
              onClick={handleSelectAll}
              className="px-4 py-2 text-sm font-medium text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded"
            >
              {allSelected ? 'Deselect All' : 'Select All'}
            </button>
          </div>

          <div className="divide-y divide-gray-200">
            {/* Base Tools */}
            {baseTools.length > 0 && (
              <div className="p-6">
                <h3 className="text-md font-semibold text-gray-900 mb-4">Built-in Tools</h3>
                <div className="space-y-3">
                  {baseTools.map((tool) => (
                    <div
                      key={tool.name}
                      className="flex items-start space-x-3 p-3 rounded-lg hover:bg-gray-50"
                    >
                      <input
                        type="checkbox"
                        id={tool.name}
                        checked={selectedTools.has(tool.name)}
                        onChange={() => handleToolToggle(tool.name)}
                        className="mt-1 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                      />
                      <label htmlFor={tool.name} className="flex-1 cursor-pointer">
                        <div className="font-medium text-gray-900">{tool.name}</div>
                        {tool.description && (
                          <div className="text-sm text-gray-600 mt-1">{tool.description}</div>
                        )}
                      </label>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* MCP Tools */}
            {mcpTools.length > 0 && (
              <div className="p-6">
                <h3 className="text-md font-semibold text-gray-900 mb-4">MCP Tools</h3>
                <div className="space-y-3">
                  {mcpTools.map((tool) => (
                    <div
                      key={tool.name}
                      className="flex items-start space-x-3 p-3 rounded-lg hover:bg-gray-50"
                    >
                      <input
                        type="checkbox"
                        id={tool.name}
                        checked={selectedTools.has(tool.name)}
                        onChange={() => handleToolToggle(tool.name)}
                        className="mt-1 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                      />
                      <label htmlFor={tool.name} className="flex-1 cursor-pointer">
                        <div className="font-medium text-gray-900">
                          {tool.mcp_tool_name || tool.name.replace('mcp_', '')}
                          <span className="ml-2 text-xs text-gray-500">(MCP)</span>
                        </div>
                        {tool.description && (
                          <div className="text-sm text-gray-600 mt-1">{tool.description}</div>
                        )}
                      </label>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {availableTools.length === 0 && (
              <div className="p-6 text-center text-gray-500">
                No tools available. Make sure MCP integrations are configured.
              </div>
            )}
          </div>

          {/* Footer with Save Button */}
          <div className="border-t border-gray-200 px-6 py-4 flex items-center justify-end space-x-4">
            <button
              onClick={() => router.push('/settings/profile')}
              className="px-4 py-2 text-gray-700 hover:text-gray-900"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? 'Saving...' : 'Save Preferences'}
            </button>
          </div>
        </div>

        {/* Info Box */}
        <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <p className="text-sm text-blue-800">
            <strong>Note:</strong> Only enabled tools will be available to your AI assistant during conversations.
            You can change these preferences at any time.
          </p>
        </div>
      </div>
    </div>
  )
}

export default function ToolsPreferencesPage() {
  return (
    <ProtectedRoute>
      <ToolsPreferencesContent />
    </ProtectedRoute>
  )
}

