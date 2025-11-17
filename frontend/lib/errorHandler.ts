/**
 * Global Error Handler
 * Catches unhandled errors and promise rejections
 */

import { trackError } from './tracing'

export function setupGlobalErrorHandlers() {
  if (typeof window === 'undefined') {
    return
  }

  // Handle unhandled errors
  window.addEventListener('error', (event) => {
    trackError(
      event.error || new Error(event.message),
      'GlobalErrorHandler',
      {
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
      }
    )
  })

  // Handle unhandled promise rejections
  window.addEventListener('unhandledrejection', (event) => {
    const error = event.reason instanceof Error 
      ? event.reason 
      : new Error(String(event.reason))
    
    trackError(
      error,
      'UnhandledPromiseRejection',
      {
        reason: event.reason,
      }
    )
  })
}

