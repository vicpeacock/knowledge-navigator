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
    
    // Set a timeout to prevent infinite loading
    const loadingTimeout = setTimeout(() => {
      console.warn('[AuthContext] Loading timeout reached, setting isLoading to false')
      setIsLoading(false)
    }, 10000) // 10 second timeout
    
    if (storedToken) {
      setToken(storedToken)
      // Try to get user info
      checkAuth().finally(() => {
        clearTimeout(loadingTimeout)
      })
    } else {
      clearTimeout(loadingTimeout)
      setIsLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // checkAuth is stable (useCallback with no deps)

  const checkAuth = useCallback(async () => {
    try {
      const storedToken = localStorage.getItem('access_token')
      if (!storedToken) {
        setUser(null)
        setToken(null)
        setIsLoading(false)
        return
      }

      setToken(storedToken)
      
      // Add timeout to prevent hanging
      const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('Auth check timeout')), 8000)
      })
      
      const response = await Promise.race([
        authApi.me(),
        timeoutPromise
      ]) as any
      
      setUser(response.data)
      setIsLoading(false)
    } catch (error: any) {
      // Token invalid or expired - try to refresh
      console.error('Auth check failed:', error)
      
      // If timeout, don't try to refresh
      if (error.message === 'Auth check timeout') {
        console.warn('[AuthContext] Auth check timed out, clearing tokens')
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        setUser(null)
        setToken(null)
        setIsLoading(false)
        return
      }
      
      // Try to refresh token if we have a refresh token
      const storedRefreshToken = localStorage.getItem('refresh_token')
      if (storedRefreshToken && error.response?.status === 401) {
        try {
          // Call refresh API directly to avoid circular dependency
          const refreshResponse = await authApi.refresh({ refresh_token: storedRefreshToken })
          const { access_token } = refreshResponse.data
          
          localStorage.setItem('access_token', access_token)
          setToken(access_token)
          
          // Retry checkAuth after refresh (with timeout)
          const timeoutPromise = new Promise((_, reject) => {
            setTimeout(() => reject(new Error('Auth check timeout')), 8000)
          })
          
          const retryResponse = await Promise.race([
            authApi.me(),
            timeoutPromise
          ]) as any
          
          setUser(retryResponse.data)
          setIsLoading(false)
          return
        } catch (refreshError: any) {
          console.error('Token refresh failed:', refreshError)
          // Fall through to clear tokens
        }
      }
      
      // Clear tokens and redirect to login
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
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

