'use client'

import { useEffect, useState } from 'react'
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
  const [backendStatus, setBackendStatus] = useState<'checking' | 'online' | 'offline'>('checking')
  const [retryCount, setRetryCount] = useState(0)

  const checkBackend = async () => {
    try {
      setBackendStatus('checking')
      const response = await axios.get(`${API_URL}/health`, {
        timeout: 5000, // 5 second timeout
      })
      
      if (response.status === 200 && response.data?.status === 'healthy') {
        setBackendStatus('online')
      } else {
        setBackendStatus('offline')
      }
    } catch (error) {
      console.error('Backend health check failed:', error)
      setBackendStatus('offline')
    }
  }

  useEffect(() => {
    checkBackend()
    
    // Retry every 5 seconds if offline
    const interval = setInterval(() => {
      if (backendStatus === 'offline') {
        checkBackend()
        setRetryCount(prev => prev + 1)
      }
    }, 5000)

    return () => clearInterval(interval)
  }, [backendStatus])

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
              {backendStatus === 'checking' ? 'Verifica in corso...' : 'Riprova'}
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

  if (backendStatus === 'checking') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">Verifica connessione al backend...</p>
        </div>
      </div>
    )
  }

  // Backend is online, render children
  return <>{children}</>
}

