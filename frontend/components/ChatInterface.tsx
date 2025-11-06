'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { sessionsApi } from '@/lib/api'
import { Message, ChatResponse } from '@/types'
import FileUpload from './FileUpload'
import FileManager from './FileManager'
import MemoryViewer from './MemoryViewer'
import { FileText, Brain } from 'lucide-react'
import { format } from 'date-fns'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useStatus } from './StatusPanel'

interface ChatInterfaceProps {
  sessionId: string
}

export default function ChatInterface({ sessionId }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingMessages, setLoadingMessages] = useState(true)
  const [useMemory, setUseMemory] = useState(true)
  const [forceWebSearch, setForceWebSearch] = useState(false)
  const [showFileManager, setShowFileManager] = useState(false)
  const [showMemoryViewer, setShowMemoryViewer] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const [isUserAtBottom, setIsUserAtBottom] = useState(true)
  const [initialLoad, setInitialLoad] = useState(true)
  const { addStatusMessage } = useStatus()

  // Load messages when sessionId changes or component mounts
  useEffect(() => {
    if (sessionId) {
      console.log('Loading messages for session:', sessionId)
      loadMessages()
    }
  }, [sessionId])

  // Scroll to bottom when messages are loaded or updated (but only if user is at bottom)
  useEffect(() => {
    if (messages.length > 0 && (isUserAtBottom || initialLoad)) {
      setTimeout(() => {
        scrollToBottom()
        setInitialLoad(false)
      }, 100)
    }
  }, [messages]) // Only depend on messages to avoid loops

  // Check if user is near bottom of scroll container
  const handleScroll = useCallback(() => {
    if (!messagesContainerRef.current) return
    
    const container = messagesContainerRef.current
    const threshold = 100 // pixels from bottom
    const isNearBottom = 
      container.scrollHeight - container.scrollTop - container.clientHeight < threshold
    
    setIsUserAtBottom(isNearBottom)
  }, [])

  useEffect(() => {
    const container = messagesContainerRef.current
    if (container) {
      container.addEventListener('scroll', handleScroll)
      return () => container.removeEventListener('scroll', handleScroll)
    }
  }, [handleScroll])

  const loadMessages = async () => {
    if (!sessionId) {
      console.warn('No sessionId provided, cannot load messages')
      setLoadingMessages(false)
      return
    }

    setLoadingMessages(true)
    try {
      console.log('Fetching messages for session:', sessionId)
      const response = await sessionsApi.getMessages(sessionId)
      console.log('Messages loaded:', response.data?.length || 0, 'messages')
      setMessages(response.data || [])
      setInitialLoad(true) // Mark as initial load to scroll to bottom
    } catch (error) {
      console.error('Error loading messages:', error)
      setMessages([]) // Set empty array on error
    } finally {
      setLoadingMessages(false)
    }
  }

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    setIsUserAtBottom(true)
  }

  // Hook per rendere le colonne delle tabelle ridimensionabili
  useEffect(() => {
    const makeTableResizable = (table: HTMLTableElement) => {
      const headers = table.querySelectorAll('thead th')
      if (headers.length === 0) return
      
      headers.forEach((header, index) => {
        const headerElement = header as HTMLElement
        
        // Skip if already has resize handler
        if (headerElement.dataset.resizable === 'true') return
        
        headerElement.dataset.resizable = 'true'
        
        // Make header relative positioned if not already
        if (getComputedStyle(headerElement).position === 'static') {
          headerElement.style.position = 'relative'
        }
        headerElement.style.userSelect = 'none'
        
        // Check if resize handle already exists
        let resizeHandle = headerElement.querySelector('.resize-handle') as HTMLElement
        if (!resizeHandle) {
          // Create resize handle
          resizeHandle = document.createElement('div')
          resizeHandle.className = 'resize-handle'
          
          // Set styles directly for better control
          resizeHandle.style.position = 'absolute'
          resizeHandle.style.top = '0'
          resizeHandle.style.right = '0'
          resizeHandle.style.width = '8px' // Wider for easier clicking
          resizeHandle.style.height = '100%'
          resizeHandle.style.cursor = 'col-resize'
          resizeHandle.style.userSelect = 'none'
          resizeHandle.style.backgroundColor = 'rgba(59, 130, 246, 0.1)' // Slightly visible by default
          resizeHandle.style.zIndex = '1000'
          resizeHandle.style.pointerEvents = 'auto'
          resizeHandle.style.touchAction = 'none'
          
          // Add hover effect via style
          resizeHandle.onmouseenter = () => {
            resizeHandle.style.backgroundColor = 'rgba(59, 130, 246, 0.5)'
          }
          resizeHandle.onmouseleave = () => {
            resizeHandle.style.backgroundColor = 'transparent'
          }
          
          console.log(`[Table Resize] Adding resize handle to column ${index}`)
          headerElement.appendChild(resizeHandle)
          
          // Verify it was added
          const verifyHandle = headerElement.querySelector('.resize-handle')
          console.log(`[Table Resize] Handle added:`, verifyHandle !== null)
        } else {
          console.log(`[Table Resize] Resize handle already exists for column ${index}`)
        }
        
        let isResizing = false
        let startX = 0
        let startWidth = 0
        let nextHeader: HTMLElement | null = null
        
        const handleMouseDown = (e: MouseEvent) => {
          e.preventDefault()
          e.stopPropagation()
          
          console.log('[Table Resize] Mouse down on resize handle', index, 'at', e.pageX)
          isResizing = true
          startX = e.pageX
          startWidth = headerElement.offsetWidth
          
          // Visual feedback
          resizeHandle.style.backgroundColor = 'rgba(59, 130, 246, 0.7)'
          
          // Get next header if exists
          const nextSibling = headerElement.nextElementSibling as HTMLElement
          if (nextSibling && nextSibling.tagName === 'TH') {
            nextHeader = nextSibling
          } else {
            nextHeader = null
          }
          
          document.addEventListener('mousemove', handleMouseMove)
          document.addEventListener('mouseup', handleMouseUp)
          document.body.style.cursor = 'col-resize'
          document.body.style.userSelect = 'none'
        }
        
        const handleMouseMove = (e: MouseEvent) => {
          if (!isResizing) return
          
          const tableElement = headerElement.closest('table') as HTMLTableElement
          if (!tableElement) return
          
          // Get table container to check max width
          const tableContainer = tableElement.closest('.overflow-x-auto') as HTMLElement
          const maxTableWidth = tableContainer ? tableContainer.clientWidth : tableElement.parentElement?.clientWidth || tableElement.offsetWidth
          
          // Calculate current total width by getting actual rendered width of the table
          // This includes all columns and borders naturally
          const currentTableWidth = tableElement.offsetWidth
          
          const diff = e.pageX - startX
          const requestedWidth = Math.max(50, startWidth + diff)
          
          // Calculate width of all other columns (excluding the one we're resizing)
          const allHeaders = tableElement.querySelectorAll('thead th')
          let otherColumnsWidth = 0
          allHeaders.forEach((h, i) => {
            if (i !== index) {
              otherColumnsWidth += (h as HTMLElement).offsetWidth
            }
          })
          
          // Calculate max width for this column: container width minus other columns
          // We use a small safety margin to account for borders and rounding
          const maxWidthForThisColumn = maxTableWidth - otherColumnsWidth - 2
          
          // Limit the width to fit in container
          const finalWidth = Math.min(requestedWidth, Math.max(50, maxWidthForThisColumn))
          
          headerElement.style.width = `${finalWidth}px`
          headerElement.style.minWidth = `${finalWidth}px`
          
          // Resize corresponding cells in all rows
          const allRows = tableElement.querySelectorAll('tr')
          allRows.forEach((row) => {
            const cell = row.children[index] as HTMLElement
            if (cell) {
              cell.style.width = `${finalWidth}px`
              cell.style.minWidth = `${finalWidth}px`
            }
          })
          
          // Adjust next column if exists and we're shrinking
          if (nextHeader && diff < 0) {
            const shrinkAmount = startWidth - finalWidth
            const nextCurrentWidth = nextHeader.offsetWidth
            
            // Calculate max width for next column too
            let nextOtherColumnsWidth = 0
            allHeaders.forEach((h, i) => {
              if (i !== index + 1) {
                nextOtherColumnsWidth += (h as HTMLElement).offsetWidth
              }
            })
            const maxWidthForNextColumn = maxTableWidth - nextOtherColumnsWidth - 2
            
            const nextWidth = Math.min(
              Math.max(50, nextCurrentWidth + shrinkAmount),
              Math.max(50, maxWidthForNextColumn)
            )
            
            nextHeader.style.width = `${nextWidth}px`
            nextHeader.style.minWidth = `${nextWidth}px`
            
            const allRows = tableElement.querySelectorAll('tr')
            allRows.forEach((row) => {
              const cell = row.children[index + 1] as HTMLElement
              if (cell) {
                cell.style.width = `${nextWidth}px`
                cell.style.minWidth = `${nextWidth}px`
              }
            })
          }
        }
        
        const handleMouseUp = () => {
          if (!isResizing) return
          
          console.log('[Table Resize] Mouse up, resizing complete')
          isResizing = false
          document.removeEventListener('mousemove', handleMouseMove)
          document.removeEventListener('mouseup', handleMouseUp)
          document.body.style.cursor = ''
          document.body.style.userSelect = ''
          resizeHandle.style.backgroundColor = 'transparent'
        }
        
        resizeHandle.addEventListener('mousedown', handleMouseDown)
      })
    }

    const initTables = () => {
      const tables = document.querySelectorAll('.resizable-table')
      console.log(`[Table Resize] Found ${tables.length} tables to make resizable`)
      tables.forEach((table, idx) => {
        console.log(`[Table Resize] Processing table ${idx + 1}`)
        makeTableResizable(table as HTMLTableElement)
      })
    }

    // Initial setup
    initTables()
    
    // Use MutationObserver to watch for new tables
    const observer = new MutationObserver(() => {
      initTables()
    })
    
    // Observe the messages container
    const messagesContainer = messagesContainerRef.current
    if (messagesContainer) {
      observer.observe(messagesContainer, {
        childList: true,
        subtree: true,
      })
    }
    
    // Also try after a delay in case tables are rendered async
    const timeoutId = setTimeout(initTables, 500)
    
    return () => {
      observer.disconnect()
      clearTimeout(timeoutId)
    }
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || loading) return

    const userMessage: Message = {
      id: '',
      session_id: sessionId,
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
      metadata: {},
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const response = await sessionsApi.chat(sessionId, input, useMemory, forceWebSearch)
      console.log('Chat response received:', response.data)
      
      // Check if response is valid
      if (!response.data) {
        console.error('No data in response:', response)
        throw new Error('Invalid response format: no data')
      }
      
      if (!response.data.response) {
        console.error('No response text in data:', response.data)
        throw new Error('Invalid response format: no response text')
      }
      
      // Add tool details to status panel if available
      if (response.data.tool_details && response.data.tool_details.length > 0) {
        response.data.tool_details.forEach((tool: any) => {
          const toolName = tool.tool_name || 'unknown'
          
          // Format parameters (extract query if present)
          let paramsText = ''
          if (tool.parameters) {
            if (tool.parameters.query) {
              paramsText = `Query: "${tool.parameters.query}"`
            } else {
              const paramsStr = JSON.stringify(tool.parameters, null, 2)
              if (paramsStr.length < 100) {
                paramsText = `Parametri: ${paramsStr}`
              } else {
                paramsText = `Parametri: ${paramsStr.substring(0, 100)}...`
              }
            }
          }
          
          // Format result preview
          let resultText = ''
          if (tool.result && tool.success) {
            if (typeof tool.result === 'string') {
              resultText = tool.result.substring(0, 150) + (tool.result.length > 150 ? '...' : '')
            } else if (tool.result.content) {
              resultText = tool.result.content.substring(0, 150) + (tool.result.content.length > 150 ? '...' : '')
            } else if (tool.result.result) {
              const resultStr = typeof tool.result.result === 'string' 
                ? tool.result.result 
                : JSON.stringify(tool.result.result, null, 2)
              resultText = resultStr.substring(0, 150) + (resultStr.length > 150 ? '...' : '')
            } else {
              const resultStr = JSON.stringify(tool.result, null, 2)
              resultText = resultStr.substring(0, 150) + (resultStr.length > 150 ? '...' : '')
            }
          }
          
          // Build message
          const parts = [`🔧 Tool: ${toolName}`]
          if (paramsText) parts.push(paramsText)
          if (resultText) parts.push(`Risultato: ${resultText}`)
          if (tool.error) parts.push(`❌ Errore: ${tool.error}`)
          
          addStatusMessage(
            tool.success ? 'info' : 'error',
            parts.join('\n')
          )
        })
      }
      
      const assistantMessage: Message = {
        id: '',
        session_id: sessionId,
        role: 'assistant',
        content: response.data.response,
        timestamp: new Date().toISOString(),
        metadata: {
          memory_used: response.data.memory_used || {},
          tools_used: response.data.tools_used || [],
          // Don't store tool_details in metadata - they're shown in status panel
        },
      }
      
      console.log('Adding assistant message:', assistantMessage)
      setMessages((prev) => [...prev, assistantMessage])
      // Note: Messages are already saved on server, we don't need to reload
      // The local messages have temporary IDs which is fine for display
    } catch (error: any) {
      console.error('Error sending message:', error)
      console.error('Error details:', {
        message: error.message,
        response: error.response?.data,
        status: error.response?.status,
      })
      const errorMessage: Message = {
        id: '',
        session_id: sessionId,
        role: 'assistant',
        content: `Errore: ${error.response?.data?.detail || error.message || 'Errore sconosciuto'}`,
        timestamp: new Date().toISOString(),
        metadata: {},
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between p-4 border-b bg-white dark:bg-gray-800">
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={useMemory}
              onChange={(e) => setUseMemory(e.target.checked)}
              className="rounded"
            />
            <span className="text-sm">Use Memory</span>
          </label>
          <label className="flex items-center gap-2" title="Forza ricerca web (come toggle Ollama)">
            <input
              type="checkbox"
              checked={forceWebSearch}
              onChange={(e) => setForceWebSearch(e.target.checked)}
              className="rounded"
            />
            <span className="text-sm">🌐 Web Search</span>
          </label>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowMemoryViewer(true)}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-sm"
            title="Visualizza contenuto memoria"
          >
            <Brain size={16} />
            Memoria
          </button>
          <button
            onClick={() => setShowFileManager(true)}
            className="flex items-center gap-2 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 text-sm"
            title="Visualizza file in memoria"
          >
            <FileText size={16} />
            File
          </button>
          <FileUpload sessionId={sessionId} onUploaded={() => setShowFileManager(false)} />
        </div>
      </div>

      <FileManager
        sessionId={sessionId}
        isOpen={showFileManager}
        onClose={() => setShowFileManager(false)}
        onFileUploaded={() => {}}
      />

      <MemoryViewer
        sessionId={sessionId}
        isOpen={showMemoryViewer}
        onClose={() => setShowMemoryViewer(false)}
      />

      <div 
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto p-4 space-y-4"
        style={{ scrollBehavior: 'smooth' }}
      >
        {loadingMessages ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="flex gap-2 justify-center mb-4">
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
              </div>
              <p className="text-gray-500">Caricamento messaggi...</p>
            </div>
          </div>
        ) : messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
              <p className="text-lg mb-2">Nessun messaggio ancora</p>
              <p className="text-sm">Inizia una conversazione inviando un messaggio</p>
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id || message.timestamp}
              className={`flex w-full ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              style={{ overflowX: 'auto', minWidth: 0 }}
            >
              <div className={`flex flex-col ${message.role === 'user' ? 'max-w-2xl items-end' : 'w-full max-w-full items-start'}`}>
                <div
                  className={`rounded-lg p-4 w-full ${
                    message.role === 'user'
                      ? 'bg-blue-600 text-white max-w-2xl'
                      : 'bg-gray-200 dark:bg-gray-700'
                  }`}
                  style={message.role === 'assistant' ? { overflowX: 'auto', minWidth: 0, maxWidth: '100%', width: '100%' } : {}}
                >
                  {message.role === 'assistant' ? (
                    <div className="max-w-none break-words">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          // Custom styling for code blocks
                          code: ({ node, inline, className, children, ...props }: any) => {
                            return inline ? (
                              <code className="bg-gray-300 dark:bg-gray-600 px-1 py-0.5 rounded text-sm" {...props}>
                                {children}
                              </code>
                            ) : (
                              <code className={className} {...props}>
                                {children}
                              </code>
                            )
                          },
                          // Custom styling for pre blocks
                          pre: ({ children, ...props }) => (
                            <pre className="bg-gray-800 text-gray-100 p-3 rounded overflow-x-auto" {...props}>
                              {children}
                            </pre>
                          ),
                          // Custom styling for links
                          a: ({ children, ...props }) => (
                            <a className="text-blue-600 dark:text-blue-400 hover:underline" {...props}>
                              {children}
                            </a>
                          ),
                          // Custom styling for lists
                          ul: ({ children, ...props }) => (
                            <ul className="list-disc list-inside my-2 space-y-1" {...props}>
                              {children}
                            </ul>
                          ),
                          ol: ({ children, ...props }) => (
                            <ol className="list-decimal list-inside my-2 space-y-1" {...props}>
                              {children}
                            </ol>
                          ),
                          // Custom styling for headings
                          h1: ({ children, ...props }) => (
                            <h1 className="text-xl font-bold mt-4 mb-2" {...props}>
                              {children}
                            </h1>
                          ),
                          h2: ({ children, ...props }) => (
                            <h2 className="text-lg font-bold mt-3 mb-2" {...props}>
                              {children}
                            </h2>
                          ),
                          h3: ({ children, ...props }) => (
                            <h3 className="text-base font-bold mt-2 mb-1" {...props}>
                              {children}
                            </h3>
                          ),
                          // Custom styling for blockquotes
                          blockquote: ({ children, ...props }) => (
                            <blockquote className="border-l-4 border-gray-400 pl-4 italic my-2" {...props}>
                              {children}
                            </blockquote>
                          ),
                          // Custom styling for paragraphs
                          p: ({ children, ...props }) => (
                            <p className="my-2" {...props}>
                              {children}
                            </p>
                          ),
                          // Custom styling for tables
                          table: ({ children, ...props }) => (
                            <div 
                              className="my-4 w-full overflow-x-auto" 
                              style={{ 
                                width: '100%',
                              }}
                            >
                              <table className="resizable-table border-collapse border border-gray-300 dark:border-gray-600 w-full" style={{ tableLayout: 'auto', width: '100%' }} {...props}>
                                {children}
                              </table>
                            </div>
                          ),
                          thead: ({ children, ...props }) => (
                            <thead className="bg-gray-100 dark:bg-gray-800" {...props}>
                              {children}
                            </thead>
                          ),
                          tbody: ({ children, ...props }) => (
                            <tbody {...props}>
                              {children}
                            </tbody>
                          ),
                          tr: ({ children, ...props }) => (
                            <tr className="border-b border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors" {...props}>
                              {children}
                            </tr>
                          ),
                          th: ({ children, ...props }) => (
                            <th 
                              className="border border-gray-300 dark:border-gray-600 px-4 py-2 text-left font-semibold text-gray-900 dark:text-gray-100 bg-gray-200 dark:bg-gray-700 relative" 
                              style={{ 
                                position: 'relative', 
                                overflow: 'visible',
                                paddingRight: '8px' // Add extra padding on right for resize area
                              }}
                              {...props}
                            >
                              {children}
                            </th>
                          ),
                          td: ({ children, ...props }) => (
                            <td className="border border-gray-300 dark:border-gray-600 px-4 py-2 text-gray-800 dark:text-gray-200" {...props}>
                              {children}
                            </td>
                          ),
                        }}
                      >
                        {message.content}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <div className="whitespace-pre-wrap break-words">{message.content}</div>
                  )}
                  {(message.metadata?.memory_used || message.metadata?.tools_used) && (
                    <div className={`text-xs mt-2 opacity-75 ${message.role === 'user' ? 'text-blue-100' : 'text-gray-600 dark:text-gray-400'}`}>
                      {message.metadata?.memory_used && (
                        <>
                          Memory: {message.metadata.memory_used.short_term ? 'ST' : ''}{' '}
                          {message.metadata.memory_used.medium_term.length > 0 ? 'MT' : ''}{' '}
                          {message.metadata.memory_used.long_term.length > 0 ? 'LT' : ''}{' '}
                          {message.metadata.memory_used.files?.length > 0 ? `Files(${message.metadata.memory_used.files.length})` : ''}
                          {' '}
                        </>
                      )}
                      {message.metadata?.tools_used && message.metadata.tools_used.length > 0 && (
                        <span className="inline-flex items-center gap-1 text-blue-600 dark:text-blue-400 font-medium">
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          </svg>
                          Tools: {message.metadata.tools_used.join(', ')}
                        </span>
                      )}
                    </div>
                  )}
                </div>
                <div className={`text-xs text-gray-500 dark:text-gray-400 mt-1 px-2 ${message.role === 'user' ? 'text-right' : 'text-left'}`}>
                  {format(new Date(message.timestamp), 'HH:mm')}
                </div>
              </div>
            </div>
          ))
        )}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-200 dark:bg-gray-700 rounded-lg p-4">
              <div className="flex gap-2">
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
        {!isUserAtBottom && messages.length > 0 && (
          <div className="flex justify-center">
            <button
              onClick={scrollToBottom}
              className="fixed bottom-24 px-4 py-2 bg-blue-600 text-white rounded-full shadow-lg hover:bg-blue-700 transition-colors text-sm"
            >
              ↓ Nuovi messaggi
            </button>
          </div>
        )}
      </div>

      <div className="p-4 border-t bg-white dark:bg-gray-800 pb-20 relative z-10">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message..."
            className="flex-1 p-3 border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
            rows={2}
            disabled={loading}
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}

