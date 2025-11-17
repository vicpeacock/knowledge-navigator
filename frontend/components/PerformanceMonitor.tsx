'use client'

import { useEffect } from 'react'
import { trackPageLoad, setNewTraceId } from '@/lib/tracing'
import { setupGlobalErrorHandlers } from '@/lib/errorHandler'

export function PerformanceMonitor() {
  useEffect(() => {
    // Setup global error handlers
    setupGlobalErrorHandlers()

    // Initialize new trace ID for this page load
    setNewTraceId()

    // Track page load performance
    if (typeof window !== 'undefined' && 'performance' in window) {
      // Wait for page to fully load
      const handleLoad = () => {
        const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming
        if (navigation) {
          const loadTime = navigation.loadEventEnd - navigation.fetchStart
          trackPageLoad(window.location.pathname, loadTime)
        }
      }

      if (document.readyState === 'complete') {
        handleLoad()
      } else {
        window.addEventListener('load', handleLoad)
        return () => window.removeEventListener('load', handleLoad)
      }
    }
  }, [])

  return null // This component doesn't render anything
}

