'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { sessionsApi } from '@/lib/api'
import { Message, ChatResponse } from '@/types'
// FileUpload, FileManager, MemoryViewer, ToolsPreferences moved to SessionDetails
import { format } from 'date-fns'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useStatus } from './StatusPanel'
import { useAgentActivity } from './AgentActivityContext'
import DayTransitionDialog from './DayTransitionDialog'

interface ChatInterfaceProps {
  sessionId: string
  readOnly?: boolean
}

export default function ChatInterface({ sessionId, readOnly = false }: ChatInterfaceProps) {
  const router = useRouter()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingMessages, setLoadingMessages] = useState(true)
  // FileManager, MemoryViewer, ToolsPreferences modals moved to SessionDetails
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const [isUserAtBottom, setIsUserAtBottom] = useState(true)
  const [initialLoad, setInitialLoad] = useState(true)
  const { addStatusMessage } = useStatus()
  const { ingestBatch } = useAgentActivity()
  const isMountedRef = useRef(true)
  const pendingMessageTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const [dayTransitionDialog, setDayTransitionDialog] = useState<{
    isOpen: boolean
    newSessionId: string
    pendingMessage?: string  // Store the message that triggered the transition
  }>({ isOpen: false, newSessionId: '' })

  // Define loadMessages before using it in useEffect
  const loadMessages = useCallback(async () => {
    const currentSessionId = sessionId
    
    if (!currentSessionId) {
      setLoadingMessages(false)
      return
    }

    setLoadingMessages(true)
    try {
      const response = await sessionsApi.getMessages(currentSessionId)
      const messagesData = response.data || []
      setMessages(messagesData)
      setInitialLoad(true) // Mark as initial load to scroll to bottom
    } catch (error: any) {
      console.error('Error loading messages:', error)
      setMessages([]) // Set empty array on error
    } finally {
      setLoadingMessages(false)
    }
  }, [sessionId])

  // Load messages when component mounts or sessionId changes
  useEffect(() => {
    // Reset mounted flag when session changes
    isMountedRef.current = true
    
    if (!sessionId) {
      setMessages([])
      setLoadingMessages(false)
      return
    }

    // Reset state when session changes
    setMessages([])
    setInput('')
    setLoading(false)
    setLoadingMessages(true)
    setInitialLoad(true)
    setIsUserAtBottom(true)
    
    // Load messages directly
    const loadMessagesDirect = async () => {
      const currentSessionId = sessionId
      
      try {
        const response = await sessionsApi.getMessages(currentSessionId)
        const messagesData = response.data || []
        setMessages(messagesData)
        setInitialLoad(true)
      } catch (error: any) {
        console.error('Error loading messages:', error)
        setMessages([])
      } finally {
        setLoadingMessages(false)
      }
    }
    
    loadMessagesDirect().then(() => {
      // After messages are loaded, check if there's a pending message for this session (from day transition)
      const pendingMessage = sessionStorage.getItem(`pending_message_${sessionId}`)
      console.log(`[ChatInterface] Checking for pending message for session ${sessionId}:`, pendingMessage ? 'FOUND' : 'NOT FOUND')
      
      if (pendingMessage && isMountedRef.current) {
        console.log(`[ChatInterface] Found pending message, will send after delay:`, pendingMessage.substring(0, 50))
        // Remove from storage immediately to avoid duplicate sends
        sessionStorage.removeItem(`pending_message_${sessionId}`)
        
        // Clear any existing timeout
        if (pendingMessageTimeoutRef.current) {
          clearTimeout(pendingMessageTimeoutRef.current)
        }
        
        // Wait a bit more to ensure everything is ready, then send the pending message
        pendingMessageTimeoutRef.current = setTimeout(async () => {
          // Double-check component is still mounted and sessionId hasn't changed
          if (!isMountedRef.current) {
            console.log('[ChatInterface] Component unmounted, skipping pending message')
            return
          }
          
          if (!sessionId || !pendingMessage.trim()) {
            console.log('[ChatInterface] Invalid sessionId or message, skipping:', { sessionId, messageLength: pendingMessage?.length })
            return
          }
          
          const currentSessionId = sessionId // Capture current sessionId
          console.log(`[ChatInterface] Processing pending message for session ${currentSessionId}`)
          
          setInput('')
          
          // Add user message to local state immediately for better UX
          const userMessage: Message = {
            id: '',
            session_id: currentSessionId,
            role: 'user',
            content: pendingMessage,
            timestamp: new Date().toISOString(),
            metadata: {},
          }
          setMessages((prev) => [...prev, userMessage])
          
          // Verify session exists before sending
          try {
            console.log(`[ChatInterface] Verifying session ${currentSessionId} exists...`)
            await sessionsApi.get(currentSessionId)
            console.log(`[ChatInterface] Session ${currentSessionId} verified`)
          } catch (error: any) {
            console.error(`[ChatInterface] Session ${currentSessionId} does not exist yet:`, error)
            addStatusMessage('error', 'La sessione non è ancora pronta. Riprova tra un momento.')
            // Remove the user message if session doesn't exist
            setMessages((prev) => prev.filter(m => m.content !== pendingMessage || m.role !== 'user'))
            return
          }
          
          // Send message to new session
          setLoading(true)
          try {
            console.log(`[ChatInterface] ===== SENDING PENDING MESSAGE =====`)
            console.log(`[ChatInterface] Session ID: ${currentSessionId}`)
            console.log(`[ChatInterface] Message:`, pendingMessage.substring(0, 50))
            console.log(`[ChatInterface] API URL:`, process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')
            console.log(`[ChatInterface] Component mounted:`, isMountedRef.current)
            
            const response = await sessionsApi.chat(currentSessionId, pendingMessage, false)
            
            console.log(`[ChatInterface] ===== RESPONSE RECEIVED =====`)
            console.log(`[ChatInterface] Session ID: ${currentSessionId}`)
            console.log(`[ChatInterface] Response status:`, response.status)
            console.log(`[ChatInterface] Response has data:`, !!response.data)
            console.log(`[ChatInterface] Response has response text:`, !!response.data?.response)
            
            // Handle response normally
            if (response.data?.response) {
              const assistantMessage: Message = {
                id: '',
                session_id: response.data.session_id || currentSessionId,
                role: 'assistant',
                content: response.data.response,
                timestamp: new Date().toISOString(),
                metadata: {},
              }
              setMessages((prev) => [...prev, assistantMessage])
            }
            if (response.data?.agent_activity) {
              ingestBatch(response.data.agent_activity)
            }
          } catch (error: any) {
            console.error('Error sending pending message to new session:', error)
            console.error('Error details:', {
              message: error.message,
              code: error.code,
              response: error.response?.data,
              status: error.response?.status,
              request: error.request,
            })
            
            // Handle different types of errors
            let errorMessage = 'Errore di rete. Verifica la connessione.'
            
            if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
              errorMessage = 'Timeout: la richiesta ha impiegato troppo tempo. Riprova.'
            } else if (error.message === 'Network Error' || !error.response) {
              errorMessage = 'Errore di rete: impossibile raggiungere il server. Verifica la connessione.'
            } else if (error.response?.data?.detail) {
              errorMessage = error.response.data.detail
            } else if (error.response?.status === 404) {
              errorMessage = 'Sessione non trovata. La sessione potrebbe non essere ancora stata creata.'
            } else if (error.response?.status === 401) {
              errorMessage = 'Non autorizzato. Effettua nuovamente il login.'
            } else if (error.response?.status >= 500) {
              errorMessage = 'Errore del server. Riprova più tardi.'
            }
            
            addStatusMessage('error', `Errore: ${errorMessage}`)
            
            // Remove the user message if sending failed
            setMessages((prev) => prev.filter(m => m.content !== pendingMessage || m.role !== 'user'))
          } finally {
            setLoading(false)
          }
        }, 1500) // Wait 1.5 seconds for everything to be ready
      }
    })
    
    // Cleanup function
    return () => {
      isMountedRef.current = false
      if (pendingMessageTimeoutRef.current) {
        clearTimeout(pendingMessageTimeoutRef.current)
        pendingMessageTimeoutRef.current = null
      }
    }
  }, [sessionId, ingestBatch, addStatusMessage]) // Only depend on sessionId

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
      console.log('[ChatInterface] Sending chat request...', {
        sessionId,
        messageLength: input.length,
        messagePreview: input.substring(0, 50),
        timestamp: new Date().toISOString(),
      })
      
      const startTime = Date.now()
      console.log('[ChatInterface] Calling sessionsApi.chat...')
      const response = await sessionsApi.chat(sessionId, input)
      const duration = Date.now() - startTime
      console.log('[ChatInterface] sessionsApi.chat returned after', duration, 'ms')
      
      console.log('[ChatInterface] ✅ Chat response received:', {
        duration: `${duration}ms`,
        status: response.status,
        hasData: !!response.data,
        hasResponse: !!(response.data?.response),
        responseLength: response.data?.response?.length || 0,
        responsePreview: response.data?.response?.substring(0, 100) || 'EMPTY',
        toolsUsed: response.data?.tools_used?.length || 0,
        agentActivity: response.data?.agent_activity?.length || 0,
        fullResponse: response.data,
      })
      
      // Check if response is valid
      if (!response || !response.data) {
        console.error('[ChatInterface] No data in response:', response)
        // If no response data, the message might have been saved but response failed
        // Reload messages from database to get the saved response
        console.log('[ChatInterface] No data in response - reloading messages from database')
        setLoading(false)
        setTimeout(() => loadMessages(), 1000)
        return
      }
      
      // Handle agent activity even if response is empty (background tasks)
      if (response.data.agent_activity && Array.isArray(response.data.agent_activity)) {
        ingestBatch(response.data.agent_activity)
      }
      
      // Check for day transition
      if (response.data.day_transition_pending && response.data.new_session_id) {
        console.log('Day transition detected, showing dialog')
        setDayTransitionDialog({
          isOpen: true,
          newSessionId: response.data.new_session_id,
          pendingMessage: input,  // Store the message that triggered the transition
        })
        setLoading(false)
        return
      }
      
      // If response is empty, show error message instead of reloading
      if (!response.data.response || response.data.response.trim() === '') {
        console.warn('Empty response received from backend')
        const errorMessage: Message = {
          id: '',
          session_id: sessionId,
          role: 'assistant',
          content: response.data.response || 'Mi dispiace, non sono riuscito a generare una risposta. Potresti riprovare?',
          timestamp: new Date().toISOString(),
          metadata: {},
        }
        setMessages((prev) => [...prev, errorMessage])
        setLoading(false)
        return
      }

      // Handle high urgency notifications (contradictions, etc.)
      if (response.data.high_urgency_notifications && response.data.high_urgency_notifications.length > 0) {
        response.data.high_urgency_notifications.forEach((notif: any) => {
          if (notif.type === 'contradiction') {
            const content = notif.content || {}
            const contradictions = content.contradictions || []
            
            if (contradictions.length > 0) {
              let notificationMsg = '⚠️ CONTRADDIZIONE RILEVATA\n\n'
              notificationMsg += 'Ho notato una contraddizione nella memoria:\n\n'
              
              contradictions.forEach((contr: any, idx: number) => {
                const newMem = contr.new_memory || ''
                const existingMem = contr.existing_memory || ''
                const explanation = contr.explanation || ''
                
                notificationMsg += `${idx + 1}. Memoria precedente: "${existingMem}"\n`
                notificationMsg += `   Memoria nuova: "${newMem}"\n`
                if (explanation) {
                  notificationMsg += `   (${explanation})\n`
                }
                notificationMsg += '\n'
              })
              
              notificationMsg += 'Quale informazione è corretta?\n'
              notificationMsg += '- A) La prima (memoria precedente)\n'
              notificationMsg += '- B) La seconda (memoria nuova)\n'
              notificationMsg += '- C) Entrambe sono corrette (spiega il contesto)\n'
              notificationMsg += '- D) Cancella entrambe'
              
              addStatusMessage('warning', notificationMsg)
            }
          }
        })
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
      console.error('[ChatInterface] ❌ Error sending message:', error)
      console.error('[ChatInterface] Error details:', {
        message: error.message,
        response: error.response?.data,
        status: error.response?.status,
        code: error.code,
        config: {
          url: error.config?.url,
          method: error.config?.method,
          timeout: error.config?.timeout,
          headers: Object.keys(error.config?.headers || {}),
        },
      })
      
      let errorMessage = error.response?.data?.detail || error.message || 'Errore sconosciuto'
      
      // If it's a network error or timeout, the message might still be processing
      if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        errorMessage = 'Timeout: la richiesta ha impiegato troppo tempo. Riprova.'
        console.log('[ChatInterface] Network error/timeout - message might be processing in background, reloading messages')
        setLoading(false)
        // Reload messages after a delay to get the response
        setTimeout(() => loadMessages(), 3000)
        addStatusMessage('info', 'Message is being processed. Refreshing...')
        return
      }
      
      if (error.message === 'Network Error' || !error.response) {
        errorMessage = 'Errore di rete: impossibile raggiungere il server. Verifica la connessione.'
      } else if (error.response?.status === 401) {
        errorMessage = 'Non autorizzato. Il token potrebbe essere scaduto. Controlla i log per il refresh.'
      }
      
      const errorMessageObj: Message = {
        id: '',
        session_id: sessionId,
        role: 'assistant',
        content: `Errore: ${errorMessage}`,
        timestamp: new Date().toISOString(),
        metadata: {},
      }
      setMessages((prev) => [...prev, errorMessageObj])
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

  const handleDayTransitionConfirm = async () => {
    // User confirmed day transition - send the message to the NEW session
    const messageToResend = dayTransitionDialog.pendingMessage
    const newSessionId = dayTransitionDialog.newSessionId
    
    if (messageToResend && messageToResend.trim() && newSessionId) {
      setInput('')
      setDayTransitionDialog({ isOpen: false, newSessionId: '', pendingMessage: undefined })
      
      // Store message in sessionStorage to send it after navigation
      sessionStorage.setItem(`pending_message_${newSessionId}`, messageToResend)
      
      // Navigate to new session - the message will be sent when component mounts
      router.push(`/sessions/${newSessionId}`)
    } else {
      setDayTransitionDialog({ isOpen: false, newSessionId: '', pendingMessage: undefined })
    }
  }

  const handleDayTransitionStay = async () => {
    // User chose to stay on previous day - resend the message to CURRENT session with proceed_with_new_day=false
    const messageToResend = dayTransitionDialog.pendingMessage
    
    if (messageToResend && messageToResend.trim()) {
      setInput('')
      setDayTransitionDialog({ isOpen: false, newSessionId: '', pendingMessage: undefined })
      setLoading(true)
      
      try {
        console.log('[ChatInterface] Resending message to current session after staying on previous day:', messageToResend.substring(0, 50))
        
        // Resend the message to the CURRENT session with proceed_with_new_day=false
        // This tells the backend to use the current session instead of the new one
        const response = await sessionsApi.chat(sessionId, messageToResend, false) // proceedWithNewDay = false
        
        console.log('[ChatInterface] ✅ Message resent successfully after staying on previous day')
        
        // Handle response normally
        if (response && response.data) {
          // Handle agent activity
          if (response.data.agent_activity && Array.isArray(response.data.agent_activity)) {
            ingestBatch(response.data.agent_activity)
          }
          
          // Add assistant response to messages
          if (response.data.response && response.data.response.trim()) {
            const assistantMessage: Message = {
              id: '',
              session_id: sessionId,
              role: 'assistant',
              content: response.data.response,
              timestamp: new Date().toISOString(),
              metadata: {},
            }
            setMessages((prev) => [...prev, assistantMessage])
          }
        }
      } catch (error: any) {
        console.error('[ChatInterface] Error resending message after staying on previous day:', error)
        addStatusMessage('Errore nell\'invio del messaggio. Riprova.', 'error')
      } finally {
        setLoading(false)
      }
    } else {
      // No message to resend, just close the dialog
      setDayTransitionDialog({ isOpen: false, newSessionId: '', pendingMessage: undefined })
    }
  }

  return (
    <div className="flex flex-col h-full">
      <DayTransitionDialog
        isOpen={dayTransitionDialog.isOpen}
        onClose={handleDayTransitionStay}
        onConfirm={handleDayTransitionConfirm}
        newSessionId={dayTransitionDialog.newSessionId}
      />

      <div 
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto p-4 pb-24 space-y-4"
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
              <p className="text-xs text-gray-400 mt-2">Session: {sessionId}</p>
            </div>
          </div>
        ) : messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
              <p className="text-lg mb-2">Nessun messaggio ancora</p>
              <p className="text-sm">Inizia una conversazione inviando un messaggio</p>
              <p className="text-xs text-gray-400 mt-2">Session: {sessionId}</p>
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

      {readOnly ? (
        <div className="p-4 border-t bg-gray-50 dark:bg-gray-900 pb-20 relative z-10">
          <div className="text-center text-gray-500 dark:text-gray-400 text-sm">
            <p className="mb-2">Questa sessione è archiviata.</p>
            <p>Puoi visualizzare i messaggi ma non puoi inviare nuovi messaggi.</p>
            <p className="mt-2 text-xs">Usa il pulsante &quot;Restore&quot; nella barra superiore per riattivarla.</p>
          </div>
        </div>
      ) : (
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
      )}
    </div>
  )
}

