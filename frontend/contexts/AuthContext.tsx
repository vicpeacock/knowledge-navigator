'use client'

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { authApi } from '@/lib/api'
import type { User, LoginRequest, RegisterRequest } from '@/types/auth'

interface AuthContextType {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (data: RegisterRequest) => Promise<void>
  logout: () => Promise<void>
  refreshToken: () => Promise<void>
  checkAuth: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()

  // Load token from localStorage on mount
  useEffect(() => {
    const storedToken = localStorage.getItem('access_token')
    const storedRefreshToken = localStorage.getItem('refresh_token')
    
    console.log('[AuthContext] Mounting, checking for token...', {
      hasToken: !!storedToken,
      hasRefreshToken: !!storedRefreshToken,
    })
    
    if (storedToken) {
      setToken(storedToken)
      // Try to get user info
      checkAuth().catch((error) => {
        // Ensure isLoading is always set to false, even if checkAuth fails unexpectedly
        console.error('[AuthContext] checkAuth failed unexpectedly:', error)
        setIsLoading(false)
      })
    } else {
      console.log('[AuthContext] No token found, setting isLoading to false immediately')
      setIsLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // checkAuth is stable (useCallback with no deps)

  const checkAuth = useCallback(async () => {
    try {
      const storedToken = localStorage.getItem('access_token')
      if (!storedToken) {
        console.log('[AuthContext] No token found, setting isLoading to false')
        setUser(null)
        setToken(null)
        setIsLoading(false)
        return
      }

      setToken(storedToken)
      console.log('[AuthContext] Checking auth with token:', storedToken.substring(0, 20) + '...')
      console.log('[AuthContext] API URL:', process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')
      
      try {
        const response = await authApi.me()
        console.log('[AuthContext] Auth check successful:', response.data)
        setUser(response.data)
        setIsLoading(false)
        return
      } catch (apiError: any) {
        // Token invalid or expired
        console.error('[AuthContext] Auth check failed:', apiError)
        console.error('[AuthContext] Error details:', {
          message: apiError.message,
          response: apiError.response?.data,
          status: apiError.response?.status,
          code: apiError.code,
        })
        
        // If 401, token is expired - clear tokens and let user login again
        // Don't try to refresh here to avoid infinite loops
        if (apiError.response?.status === 401) {
          console.log('[AuthContext] Token expired (401), clearing tokens')
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          setUser(null)
          setToken(null)
          setIsLoading(false)
          return
        }
        
        // For other errors, clear tokens anyway
        console.log('[AuthContext] Clearing tokens due to error')
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        setUser(null)
        setToken(null)
        setIsLoading(false)
        return
      }
    } catch (error: any) {
      // Catch any unexpected errors
      console.error('[AuthContext] Unexpected error in checkAuth:', error)
      // Always set isLoading to false, even on unexpected errors
      setUser(null)
      setToken(null)
      setIsLoading(false)
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    try {
      setIsLoading(true)
      const response = await authApi.login({ email, password })
      const { access_token, refresh_token, user: userData } = response.data

      // Store tokens
      localStorage.setItem('access_token', access_token)
      localStorage.setItem('refresh_token', refresh_token)
      
      // Store tenant_id for multi-tenant support
      if (userData.tenant_id) {
        localStorage.setItem('tenant_id', userData.tenant_id)
      }

      setToken(access_token)
      setUser(userData)
      setIsLoading(false)
      
      // Redirect to home
      router.push('/')
    } catch (error: any) {
      setIsLoading(false)
      const message = error.response?.data?.detail || 'Login failed'
      throw new Error(message)
    }
  }, [router])

  const register = useCallback(async (data: RegisterRequest) => {
    try {
      setIsLoading(true)
      const response = await authApi.register(data)
      setIsLoading(false)
      
      // After registration, redirect to login
      router.push('/auth/login?registered=true')
    } catch (error: any) {
      setIsLoading(false)
      const message = error.response?.data?.detail || 'Registration failed'
      throw new Error(message)
    }
  }, [router])

  const logout = useCallback(async () => {
    try {
      // Call logout endpoint if token exists
      if (token) {
        await authApi.logout()
      }
    } catch (error) {
      // Ignore logout errors
      console.error('Logout error:', error)
    } finally {
      // Clear local storage
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('tenant_id')
      
      setToken(null)
      setUser(null)
      
      // Redirect to login
      router.push('/auth/login')
    }
  }, [token, router])

  const refreshToken = useCallback(async () => {
    try {
      const storedRefreshToken = localStorage.getItem('refresh_token')
      if (!storedRefreshToken) {
        throw new Error('No refresh token available')
      }

      const response = await authApi.refresh({ refresh_token: storedRefreshToken })
      const { access_token } = response.data

      localStorage.setItem('access_token', access_token)
      setToken(access_token)
      
      return access_token
    } catch (error) {
      // Refresh failed, logout
      console.error('Token refresh failed:', error)
      await logout()
      throw error
    }
  }, [logout])

  const value: AuthContextType = {
    user,
    token,
    isAuthenticated: !!user && !!token,
    isLoading,
    login,
    register,
    logout,
    refreshToken,
    checkAuth,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
