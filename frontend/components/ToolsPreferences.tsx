'use client'

import { useState, useEffect } from 'react'
import { usersApi } from '@/lib/api'
import { ChevronUp, ChevronDown } from 'lucide-react'

interface Tool {
  name: string
  description?: string
  parameters?: any
  mcp_integration_id?: string
  mcp_tool_name?: string
  mcp_integration_name?: string
  mcp_server_name?: string
}

interface ToolsPreferencesData {
  available_tools: Tool[]
  user_preferences: string[]
}

interface ToolsPreferencesProps {
  onClose?: () => void
  showHeader?: boolean
  showCancelButton?: boolean
}

export default function ToolsPreferences({ onClose, showHeader = true, showCancelButton = false }: ToolsPreferencesProps) {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [toolsData, setToolsData] = useState<ToolsPreferencesData | null>(null)
  const [selectedTools, setSelectedTools] = useState<Set<string>>(new Set())
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [expandedServers, setExpandedServers] = useState<Set<string>>(new Set())
  const [mcpServersExpanded, setMcpServersExpanded] = useState(false)

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

  const handleSelectAllInCategory = (toolNames: string[]) => {
    const allSelected = toolNames.every(name => selectedTools.has(name))
    
    const newSelected = new Set(selectedTools)
    if (allSelected) {
      // Deselect all in this category
      toolNames.forEach(name => newSelected.delete(name))
    } else {
      // Select all in this category
      toolNames.forEach(name => newSelected.add(name))
    }
    setSelectedTools(newSelected)
  }

  const areAllSelectedInCategory = (toolNames: string[]): boolean => {
    return toolNames.length > 0 && toolNames.every(name => selectedTools.has(name))
  }

  const areSomeSelectedInCategory = (toolNames: string[]): boolean => {
    return toolNames.some(name => selectedTools.has(name)) && !areAllSelectedInCategory(toolNames)
  }

  const toggleServerExpanded = (serverName: string) => {
    const newExpanded = new Set(expandedServers)
    if (newExpanded.has(serverName)) {
      newExpanded.delete(serverName)
    } else {
      newExpanded.add(serverName)
    }
    setExpandedServers(newExpanded)
  }

  const isServerExpanded = (serverName: string): boolean => {
    return expandedServers.has(serverName)
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
      
      // Close modal if provided
      if (onClose) {
        setTimeout(() => {
          onClose()
        }, 1000)
      }
    } catch (err: any) {
      console.error('Error saving tools preferences:', err)
      setError(err.response?.data?.detail || 'Failed to save tools preferences')
    } finally {
      setSaving(false)
    }
  }

  const groupToolsByType = (tools: Tool[] | undefined) => {
    const baseTools: Tool[] = []
    // Group by integration first, then by server within each integration
    // Structure: Map<integrationId, { integrationName: string, servers: Map<serverName, tools[]> }>
    const mcpToolsByIntegration: Map<string, { 
      integrationName: string
      servers: Map<string, { serverName: string; tools: Tool[] }>
    }> = new Map()
    
    if (!tools || !Array.isArray(tools)) {
      return { baseTools, mcpToolsByIntegration }
    }
    
    tools.forEach(tool => {
      if (tool && tool.name && tool.name.startsWith('mcp_')) {
        const integrationId = tool.mcp_integration_id || 'unknown'
        const integrationName = tool.mcp_integration_name || 'Unknown MCP Server'
        const serverName = tool.mcp_server_name || 'Unknown Server'
        
        // Get or create integration entry
        if (!mcpToolsByIntegration.has(integrationId)) {
          mcpToolsByIntegration.set(integrationId, {
            integrationName,
            servers: new Map()
          })
        }
        
        const integration = mcpToolsByIntegration.get(integrationId)!
        
        // Get or create server entry within this integration
        if (!integration.servers.has(serverName)) {
          integration.servers.set(serverName, {
            serverName,
            tools: []
          })
        }
        
        integration.servers.get(serverName)!.tools.push(tool)
      } else if (tool && tool.name) {
        baseTools.push(tool)
      }
    })
    
    return { baseTools, mcpToolsByIntegration }
  }

  if (loading) {
    return (
      <div className="p-6">
        <p className="text-gray-600">Loading tools preferences...</p>
      </div>
    )
  }

  if (!toolsData) {
    return (
      <div className="p-6">
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
    )
  }

  const availableTools = toolsData.available_tools || []
  const { baseTools, mcpToolsByIntegration } = groupToolsByType(availableTools)
  const allSelected = availableTools.length > 0 && selectedTools.size === availableTools.length
  const someSelected = selectedTools.size > 0 && selectedTools.size < availableTools.length

  return (
    <div className="p-6">
      {/* Header */}
      {showHeader && (
        <div className="mb-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Tools Preferences</h1>
              <p className="mt-2 text-gray-600">
                Select which tools you want to enable for your AI assistant
              </p>
            </div>
          </div>
        </div>
      )}

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
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-md font-semibold text-gray-900">Built-in Tools</h3>
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="select-all-builtin"
                    checked={areAllSelectedInCategory(baseTools.map(t => t.name))}
                    ref={(input) => {
                      if (input) input.indeterminate = areSomeSelectedInCategory(baseTools.map(t => t.name))
                    }}
                    onChange={() => handleSelectAllInCategory(baseTools.map(t => t.name))}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                  />
                  <label htmlFor="select-all-builtin" className="text-sm text-gray-700 cursor-pointer">
                    {areAllSelectedInCategory(baseTools.map(t => t.name)) ? 'Deselect All' : 'Select All'}
                  </label>
                </div>
              </div>
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

          {/* MCP Tools - Grouped by Integration, then by Server */}
          {mcpToolsByIntegration.size > 0 && (
            Array.from(mcpToolsByIntegration.entries()).map(([integrationId, { integrationName, servers }]) => {
              // Get all tool names for this integration (across all servers)
              const allIntegrationToolNames: string[] = []
              servers.forEach(({ tools }) => {
                tools.forEach(tool => allIntegrationToolNames.push(tool.name))
              })
              const allIntegrationSelected = areAllSelectedInCategory(allIntegrationToolNames)
              const someIntegrationSelected = areSomeSelectedInCategory(allIntegrationToolNames)
              const integrationExpandedKey = `integration-${integrationId}`
              const isIntegrationExpanded = isServerExpanded(integrationExpandedKey)
              
              return (
                <div key={integrationId} className="p-6 border-b border-gray-200">
                  {/* Integration Header - Clickable to expand/collapse all servers */}
                  <div className="flex items-center justify-between mb-4">
                    <div 
                      className="flex items-center justify-between flex-1 cursor-pointer hover:bg-gray-50 rounded-lg p-2 -m-2"
                      onClick={() => toggleServerExpanded(integrationExpandedKey)}
                    >
                      <h3 className="text-md font-semibold text-gray-900">
                        {integrationName}
                        <span className="ml-2 text-xs text-gray-500 font-normal">
                          ({servers.size} server{servers.size !== 1 ? 's' : ''})
                        </span>
                      </h3>
                      {isIntegrationExpanded ? (
                        <ChevronUp size={20} className="text-gray-500" />
                      ) : (
                        <ChevronDown size={20} className="text-gray-500" />
                      )}
                    </div>
                    <div 
                      className="flex items-center space-x-2 ml-4"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <input
                        type="checkbox"
                        id={`select-all-integration-${integrationId}`}
                        checked={allIntegrationSelected}
                        ref={(input) => {
                          if (input) input.indeterminate = someIntegrationSelected
                        }}
                        onChange={() => handleSelectAllInCategory(allIntegrationToolNames)}
                        className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                      />
                      <label htmlFor={`select-all-integration-${integrationId}`} className="text-sm text-gray-700 cursor-pointer">
                        {allIntegrationSelected ? 'Deselect All' : 'Select All'}
                      </label>
                    </div>
                  </div>
                
                  {/* All Servers within this Integration - Collapsible */}
                  {isIntegrationExpanded && (
                    <div className="space-y-4">
                      {Array.from(servers.entries()).map(([serverName, { serverName: displayName, tools }]) => {
                        const toolNames = tools.map(t => t.name)
                        const allSelected = areAllSelectedInCategory(toolNames)
                        const someSelected = areSomeSelectedInCategory(toolNames)
                        const isExpanded = isServerExpanded(serverName)
                        
                        return (
                          <div key={serverName} className="pl-4 border-l-2 border-gray-200">
                            {/* Server Header - Clickable to expand/collapse */}
                            <div 
                              className="flex items-center justify-between cursor-pointer hover:bg-gray-50 rounded-lg p-2 -m-2"
                              onClick={() => toggleServerExpanded(serverName)}
                            >
                              <h4 className="text-sm font-semibold text-gray-900">
                                {displayName}
                                <span className="ml-2 text-xs text-gray-500 font-normal">(MCP Server)</span>
                              </h4>
                              <div className="flex items-center space-x-3">
                                <div 
                                  className="flex items-center space-x-2"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  <input
                                    type="checkbox"
                                    id={`select-all-${serverName}`}
                                    checked={allSelected}
                                    ref={(input) => {
                                      if (input) input.indeterminate = someSelected
                                    }}
                                    onChange={() => handleSelectAllInCategory(toolNames)}
                                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                                  />
                                  <label htmlFor={`select-all-${serverName}`} className="text-sm text-gray-700 cursor-pointer">
                                    {allSelected ? 'Deselect All' : 'Select All'}
                                  </label>
                                </div>
                                {isExpanded ? (
                                  <ChevronUp size={18} className="text-gray-500" />
                                ) : (
                                  <ChevronDown size={18} className="text-gray-500" />
                                )}
                              </div>
                            </div>
                            
                            {/* Tools List - Collapsible */}
                            {isExpanded && (
                              <div className="mt-4 space-y-3">
                                {tools.map((tool) => (
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
                                      </div>
                                      {tool.description && (
                                        <div className="text-sm text-gray-600 mt-1">{tool.description}</div>
                                      )}
                                    </label>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
                )
              })
            )}

          {availableTools.length === 0 && (
            <div className="p-6 text-center text-gray-500">
              No tools available. Make sure MCP integrations are configured.
            </div>
          )}
        </div>

        {/* Footer with Save Button */}
        <div className="border-t border-gray-200 px-6 py-4 flex items-center justify-end space-x-4">
          {showCancelButton && onClose && (
            <button
              onClick={onClose}
              className="px-4 py-2 text-gray-700 hover:text-gray-900"
            >
              Cancel
            </button>
          )}
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
  )
}

