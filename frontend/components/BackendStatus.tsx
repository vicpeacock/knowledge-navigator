'use client'

import { useEffect, useState, useRef } from 'react'
import axios from 'axios'

// For testing: set TEST_BACKEND_OFFLINE=true to simulate offline backend
const TEST_BACKEND_OFFLINE = typeof window !== 'undefined' && 
  new URLSearchParams(window.location.search).get('test_offline') === 'true'

const API_URL = TEST_BACKEND_OFFLINE 
  ? 'http://localhost:9999' // Invalid port to simulate offline
  : (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')

interface BackendStatusProps {
  children: React.ReactNode
}

export function BackendStatus({ children }: BackendStatusProps) {
  type Status = 'checking' | 'online' | 'offline' | 'degraded'
  const [backendStatus, setBackendStatus] = useState<Status>('checking')
  const [retryCount, setRetryCount] = useState(0)
  const [unhealthyMandatory, setUnhealthyMandatory] = useState<
    Array<{ service: string; error?: string; message?: string }>
  >([])
  const statusRef = useRef<Status>('checking')

  const checkBackend = async () => {
    try {
      setBackendStatus('checking')
      statusRef.current = 'checking'
      console.log(`[BackendStatus] Checking backend at ${API_URL}/health`)
      const response = await axios.get(`${API_URL}/health`, {
        timeout: 2000, // 2 second timeout for faster feedback
        headers: {
          'Accept': 'application/json',
        },
        validateStatus: (status) => status < 500, // Accept 4xx as valid responses
      })
      
      console.log(`[BackendStatus] Backend responded with status ${response.status}`)
      
      // Check if backend is responding (even if some services are unhealthy)
      if (response.status === 200 && response.data) {
        const data = response.data

        const mandatoryIssues =
          data?.unhealthy_mandatory_services ??
          Object.entries(data?.services ?? {})
            .filter(([, status]: [string, any]) => status?.mandatory && !status?.healthy)
            .map(([service, status]: [string, any]) => ({
              service,
              error: status?.error,
              message: status?.message,
            }))

        setUnhealthyMandatory(mandatoryIssues)

        if (mandatoryIssues.length > 0) {
          const newStatus: Status = 'degraded'
          console.log(`[BackendStatus] Backend is degraded, ${mandatoryIssues.length} mandatory services unhealthy`)
          setBackendStatus(newStatus)
          statusRef.current = newStatus
        } else {
          const newStatus: Status = 'online'
          console.log('[BackendStatus] Backend is online')
          setBackendStatus(newStatus)
          statusRef.current = newStatus
          setRetryCount(0)
        }
      } else {
        const newStatus: Status = 'offline'
        console.warn('[BackendStatus] Backend responded but with invalid data')
        setBackendStatus(newStatus)
        statusRef.current = newStatus
      }
    } catch (error: any) {
      console.error('[BackendStatus] Backend health check failed:', error)
      if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        console.warn('[BackendStatus] Backend health check timeout')
      } else if (error.response) {
        console.error('[BackendStatus] Backend responded with error:', error.response.status, error.response.data)
      } else if (error.request) {
        console.error('[BackendStatus] No response from backend:', error.request)
      }
      const newStatus: Status = 'offline'
      setBackendStatus(newStatus)
      statusRef.current = newStatus
    }
  }

  useEffect(() => {
    let mounted = true
    
    console.log('[BackendStatus] Component mounted, starting health check')
    
    const performCheck = async () => {
      if (mounted) {
        await checkBackend()
      }
    }
    
    // Initial check
    performCheck()
    
    // Retry every 5 seconds if offline or degraded
    const interval = setInterval(() => {
      if (mounted && (statusRef.current === 'offline' || statusRef.current === 'degraded')) {
        console.log('[BackendStatus] Retrying health check (status:', statusRef.current, ')')
        performCheck()
        setRetryCount(prev => prev + 1)
      }
    }, 5000)

    return () => {
      console.log('[BackendStatus] Component unmounting')
      mounted = false
      clearInterval(interval)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Empty dependency array - only run on mount

  if (backendStatus === 'offline') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="max-w-md w-full bg-white dark:bg-gray-800 rounded-lg shadow-lg p-8 text-center">
          <div className="mb-6">
            <svg
              className="mx-auto h-16 w-16 text-red-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
            Backend non disponibile
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mb-6">
            Il backend non risponde. Verifica che il server sia in esecuzione su{' '}
            <code className="bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded text-sm">
              {API_URL}
            </code>
          </p>
          <div className="space-y-3">
            <button
              onClick={checkBackend}
              className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Riprova
            </button>
            {retryCount > 0 && (
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Tentativi di riconnessione: {retryCount}
              </p>
            )}
          </div>
          <div className="mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Suggerimenti:
            </p>
            <ul className="text-xs text-gray-500 dark:text-gray-400 mt-2 text-left space-y-1">
              <li>• Verifica che il backend sia avviato</li>
              <li>• Controlla che la porta 8000 sia libera</li>
              <li>• Verifica i log del backend per errori</li>
            </ul>
          </div>
        </div>
      </div>
    )
  }

  if (backendStatus === 'degraded') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="max-w-xl w-full bg-white dark:bg-gray-800 rounded-lg shadow-lg p-8 text-center space-y-6">
          <div>
            <svg
              className="mx-auto h-16 w-16 text-yellow-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
              Servizi non disponibili
            </h1>
            <p className="text-gray-600 dark:text-gray-400">
              Il backend risponde ma alcuni servizi critici sono offline. Riattivali prima di continuare.
            </p>
          </div>

          <div className="bg-gray-100 dark:bg-gray-700 rounded-lg p-4 text-left space-y-2">
            <p className="text-sm font-semibold text-gray-700 dark:text-gray-200">
              Servizi da risolvere:
            </p>
            <ul className="space-y-2">
              {unhealthyMandatory.map(item => (
                <li key={item.service} className="text-sm text-gray-600 dark:text-gray-300">
                  <span className="font-semibold text-gray-800 dark:text-gray-100">{item.service}</span>
                  {item.error ? ` — ${item.error}` : item.message ? ` — ${item.message}` : null}
                </li>
              ))}
            </ul>
          </div>

          <div className="space-y-3">
            <button
              onClick={checkBackend}
              className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Riprova
            </button>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Suggerimenti:
              <br />• Avvia ChromaDB (`docker compose up -d chromadb`)
              <br />• Avvia il background LLM se richiesto (`tools/infra/start_llama_background.sh`)
            </p>
          </div>
        </div>
      </div>
    )
  }

  if (backendStatus === 'checking') {
    // Render children even while checking - show overlay instead of blocking
    // Use lower z-index so popups can appear above it
    return (
      <>
        {children}
        <div className="fixed inset-0 bg-gray-50/80 dark:bg-gray-900/80 backdrop-blur-sm flex items-center justify-center z-40 pointer-events-none">
          <div className="text-center bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg pointer-events-auto">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
            <p className="text-gray-600 dark:text-gray-400">Verifica connessione al backend...</p>
          </div>
        </div>
      </>
    )
  }

  // Backend is online, render children
  return <>{children}</>
}

