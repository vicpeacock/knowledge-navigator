'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'

interface ProtectedRouteProps {
  children: React.ReactNode
  requireAdmin?: boolean
}

export function ProtectedRoute({ children, requireAdmin = false }: ProtectedRouteProps) {
  console.log('[ProtectedRoute] Component rendering')
  const { isAuthenticated, user, isLoading } = useAuth()
  const router = useRouter()
  
  console.log('[ProtectedRoute] Auth state:', { isAuthenticated, isLoading, hasUser: !!user })

  useEffect(() => {
    if (!isLoading) {
      if (!isAuthenticated) {
        router.push('/auth/login')
        return
      }

      if (requireAdmin && user?.role !== 'admin') {
        router.push('/')
        return
      }
    }
  }, [isAuthenticated, isLoading, user, requireAdmin, router])

  // Show loading state while checking auth
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">Loading...</p>
        </div>
      </div>
    )
  }

  // Don't render children if not authenticated
  if (!isAuthenticated) {
    return null
  }

  // Don't render children if admin required but user is not admin
  if (requireAdmin && user?.role !== 'admin') {
    return null
  }

  return <>{children}</>
}

