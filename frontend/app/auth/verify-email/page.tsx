'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { authApi } from '@/lib/api'

export const dynamic = 'force-dynamic'

export default function VerifyEmailPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState<string>('')
  const [userEmail, setUserEmail] = useState<string | null>(null)

  useEffect(() => {
    const verifyEmail = async () => {
      const token = searchParams.get('token')

      if (!token) {
        setStatus('error')
        setMessage('Token di verifica mancante. Controlla il link nell\'email.')
        return
      }

      try {
        // Decode URL-encoded token if needed
        const decodedToken = decodeURIComponent(token)
        console.log('Verifying email with token:', decodedToken.substring(0, 20) + '...')
        
        const response = await authApi.verifyEmail(decodedToken)
        
        // Check if already verified (success case)
        if (response.data.already_verified) {
          setStatus('success')
          setMessage('Email già verificata in precedenza!')
        } else {
          setStatus('success')
          setMessage(response.data.message || 'Email verificata con successo!')
        }
        
        // If the response includes user email, show it
        if (response.data.email) {
          setUserEmail(response.data.email)
        }

        // If backend provided a password_reset_token, redirect to password setup page
        if (response.data.password_reset_token) {
          const resetToken = response.data.password_reset_token as string
          console.log('Redirecting to password setup with token:', resetToken.substring(0, 20) + '...')
          router.push(`/auth/password-reset/confirm?token=${encodeURIComponent(resetToken)}`)
        }
      } catch (error: any) {
        console.error('Email verification error:', error)
        
        // Check if it's a network/connection error
        if (error.code === 'ECONNABORTED' || error.message?.includes('timeout') || error.message?.includes('Network Error') || !error.response) {
          setStatus('error')
          setMessage('Backend non disponibile. Riprova tra qualche secondo.')
          return
        }
        
        setStatus('error')
        const errorMessage = error.response?.data?.detail || error.message || 'Errore durante la verifica dell\'email'
        
        // If error mentions token already used, show as info instead of error
        if (errorMessage.includes('already been used') || errorMessage.includes('già verificata')) {
          setStatus('success')
          setMessage('Email già verificata! Puoi procedere al login.')
        } else {
          setMessage(errorMessage)
        }
      }
    }

    verifyEmail()
  }, [searchParams])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900 dark:text-white">
            Verifica Email
          </h2>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-8">
          {status === 'loading' && (
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
              <p className="mt-4 text-gray-600 dark:text-gray-400">Verifica email in corso...</p>
            </div>
          )}

          {status === 'success' && (
            <div className="text-center">
              <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-green-100 dark:bg-green-900">
                <svg
                  className="h-6 w-6 text-green-600 dark:text-green-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              </div>
              <h3 className="mt-4 text-lg font-medium text-gray-900 dark:text-white">
                Email verificata!
              </h3>
              <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                {message}
              </p>
              {userEmail && (
                <p className="mt-2 text-sm text-gray-500 dark:text-gray-500">
                  Email: {userEmail}
                </p>
              )}
              <div className="mt-6">
                <Link
                  href="/auth/login"
                  className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  Vai al Login
                </Link>
              </div>
            </div>
          )}

          {status === 'error' && (
            <div className="text-center">
              <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100 dark:bg-red-900">
                <svg
                  className="h-6 w-6 text-red-600 dark:text-red-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </div>
              <h3 className="mt-4 text-lg font-medium text-gray-900 dark:text-white">
                Errore di verifica
              </h3>
              <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                {message}
              </p>
              <div className="mt-6 space-y-2">
                <Link
                  href="/auth/login"
                  className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  Vai al Login
                </Link>
                <Link
                  href="/auth/register"
                  className="w-full flex justify-center py-2 px-4 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 hover:bg-gray-50 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  Registrati
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

