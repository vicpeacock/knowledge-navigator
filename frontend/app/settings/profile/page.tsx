'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useAuth } from '@/contexts/AuthContext'
import { authApi, usersApi, integrationsApi } from '@/lib/api'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { ExternalLink, CheckCircle, XCircle } from 'lucide-react'

// Common timezones
const TIMEZONES = [
  { value: 'UTC', label: 'UTC (Coordinated Universal Time)' },
  { value: 'Europe/Rome', label: 'Europe/Rome (Italy)' },
  { value: 'Europe/London', label: 'Europe/London (UK)' },
  { value: 'Europe/Paris', label: 'Europe/Paris (France)' },
  { value: 'Europe/Berlin', label: 'Europe/Berlin (Germany)' },
  { value: 'Europe/Madrid', label: 'Europe/Madrid (Spain)' },
  { value: 'America/New_York', label: 'America/New_York (US Eastern)' },
  { value: 'America/Chicago', label: 'America/Chicago (US Central)' },
  { value: 'America/Denver', label: 'America/Denver (US Mountain)' },
  { value: 'America/Los_Angeles', label: 'America/Los_Angeles (US Pacific)' },
  { value: 'America/Toronto', label: 'America/Toronto (Canada Eastern)' },
  { value: 'America/Vancouver', label: 'America/Vancouver (Canada Pacific)' },
  { value: 'Asia/Tokyo', label: 'Asia/Tokyo (Japan)' },
  { value: 'Asia/Shanghai', label: 'Asia/Shanghai (China)' },
  { value: 'Asia/Dubai', label: 'Asia/Dubai (UAE)' },
  { value: 'Australia/Sydney', label: 'Australia/Sydney' },
  { value: 'Australia/Melbourne', label: 'Australia/Melbourne' },
]

function ProfileContent() {
  const { user } = useAuth()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [profileLoading, setProfileLoading] = useState(true)
  const [profileData, setProfileData] = useState<{ name?: string; timezone?: string }>({})
  const [profileError, setProfileError] = useState<string | null>(null)
  const [profileSuccess, setProfileSuccess] = useState<string | null>(null)
  const [profileSaving, setProfileSaving] = useState(false)
  const [backgroundServicesLoading, setBackgroundServicesLoading] = useState(true)
  const [backgroundServicesData, setBackgroundServicesData] = useState<{ email_notifications_enabled: boolean; calendar_notifications_enabled: boolean }>({
    email_notifications_enabled: true,
    calendar_notifications_enabled: true,
  })
  const [backgroundServicesError, setBackgroundServicesError] = useState<string | null>(null)
  const [backgroundServicesSuccess, setBackgroundServicesSuccess] = useState<string | null>(null)
  const [backgroundServicesSaving, setBackgroundServicesSaving] = useState(false)
  const [oauthIntegrationsLoading, setOAuthIntegrationsLoading] = useState(true)
  const [oauthIntegrations, setOAuthIntegrations] = useState<Array<{
    integration_id: string
    integration_name: string
    server_url: string
    oauth_required: boolean
    oauth_authorized: boolean
    google_email?: string | null
  }>>([])
  const [oauthIntegrationsError, setOAuthIntegrationsError] = useState<string | null>(null)
  const [oauthIntegrationsSuccess, setOAuthIntegrationsSuccess] = useState<string | null>(null)
  const [emailIntegrationsLoading, setEmailIntegrationsLoading] = useState(true)
  const [emailIntegrations, setEmailIntegrations] = useState<Array<{
    id: string
    provider: string
    enabled: boolean
    purpose: string
  }>>([])
  const [emailIntegrationsError, setEmailIntegrationsError] = useState<string | null>(null)
  const [emailIntegrationsSuccess, setEmailIntegrationsSuccess] = useState<string | null>(null)
  const [calendarIntegrationsLoading, setCalendarIntegrationsLoading] = useState(true)
  const [calendarIntegrations, setCalendarIntegrations] = useState<Array<{
    id: string
    provider: string
    enabled: boolean
    purpose: string
  }>>([])
  const [calendarIntegrationsError, setCalendarIntegrationsError] = useState<string | null>(null)
  const [calendarIntegrationsSuccess, setCalendarIntegrationsSuccess] = useState<string | null>(null)

  useEffect(() => {
    // Check URL parameters once
    const urlParams = new URLSearchParams(window.location.search)
    
    // Check if we're returning from MCP OAuth callback
    if (urlParams.get('oauth_success') === 'true') {
      // OAuth authorization completed - verify we still have auth token
      const token = localStorage.getItem('access_token')
      if (!token) {
        // Token lost during OAuth redirect - try to restore from sessionStorage
        const redirectBack = sessionStorage.getItem('oauth_redirect_back')
        sessionStorage.removeItem('oauth_redirect_back')
        sessionStorage.removeItem('oauth_integration_id')
        
        // Redirect to login with return URL
        const loginUrl = redirectBack 
          ? `/auth/login?redirect=${encodeURIComponent(redirectBack)}&oauth_success=true`
          : '/auth/login?redirect=/settings/profile&oauth_success=true'
        window.location.href = loginUrl
        return
      }
      // Clean URL first to avoid issues
      window.history.replaceState({}, document.title, '/settings/profile')
      // Clean up sessionStorage
      sessionStorage.removeItem('oauth_redirect_back')
      sessionStorage.removeItem('oauth_integration_id')
      // Then reload integrations
      loadOAuthIntegrations()
      setOAuthIntegrationsSuccess('OAuth authorization completed successfully!')
    } 
    // Check if we're returning from email/calendar OAuth callback
    else if (urlParams.get('success') === 'true' && urlParams.get('integration_id')) {
      // OAuth callback completed - reload integrations
      loadProfile()
      loadBackgroundServicesPreferences()
      loadOAuthIntegrations()
      loadEmailIntegrations()
      loadCalendarIntegrations()
      // Clean URL
      window.history.replaceState({}, document.title, '/settings/profile')
      setEmailIntegrationsSuccess('Email integration connected successfully!')
      setCalendarIntegrationsSuccess('Calendar integration connected successfully!')
    } 
    // Normal page load
    else {
      loadProfile()
      loadBackgroundServicesPreferences()
      loadOAuthIntegrations()
      loadEmailIntegrations()
      loadCalendarIntegrations()
    }
  }, [])

  const loadProfile = async () => {
    try {
      setProfileLoading(true)
      const response = await usersApi.getProfile()
      setProfileData({
        name: response.data.name || '',
        timezone: response.data.timezone || 'UTC',
      })
    } catch (err: any) {
      const errorDetail = err.response?.data?.detail
      // Check if it's an authentication error
      if (err.response?.status === 401 || (typeof errorDetail === 'string' && errorDetail.includes('Authorization header missing'))) {
        // Redirect to login - token expired or missing
        window.location.href = '/auth/login?redirect=/settings/profile'
        return
      }
      if (Array.isArray(errorDetail)) {
        // Pydantic validation errors
        setProfileError(errorDetail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(', '))
      } else if (typeof errorDetail === 'string') {
        setProfileError(errorDetail)
      } else {
        setProfileError(err.response?.data?.message || err.message || 'Failed to load profile')
      }
    } finally {
      setProfileLoading(false)
    }
  }

  const loadBackgroundServicesPreferences = async () => {
    try {
      setBackgroundServicesLoading(true)
      const response = await usersApi.getBackgroundServicesPreferences()
      setBackgroundServicesData({
        email_notifications_enabled: response.data.email_notifications_enabled ?? true,
        calendar_notifications_enabled: response.data.calendar_notifications_enabled ?? true,
      })
    } catch (err: any) {
      const errorDetail = err.response?.data?.detail
      // Check if it's an authentication error
      if (err.response?.status === 401 || (typeof errorDetail === 'string' && errorDetail.includes('Authorization header missing'))) {
        // Don't redirect here - let the profile error handle it
        setBackgroundServicesError('Authentication required. Please refresh the page or log in again.')
        return
      }
      if (Array.isArray(errorDetail)) {
        setBackgroundServicesError(errorDetail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(', '))
      } else if (typeof errorDetail === 'string') {
        setBackgroundServicesError(errorDetail)
      } else {
        setBackgroundServicesError(err.response?.data?.message || err.message || 'Failed to load background services preferences')
      }
    } finally {
      setBackgroundServicesLoading(false)
    }
  }

  const loadOAuthIntegrations = async () => {
    try {
      setOAuthIntegrationsLoading(true)
      setOAuthIntegrationsError(null)
      const response = await usersApi.getOAuthIntegrations()
      console.log('OAuth integrations response:', response.data)
      console.log('Integrations:', response.data.integrations)
      setOAuthIntegrations(response.data.integrations || [])
    } catch (err: any) {
      const errorDetail = err.response?.data?.detail
      // Check if it's an authentication error
      if (err.response?.status === 401 || (typeof errorDetail === 'string' && errorDetail.includes('Authorization header missing'))) {
        // Don't redirect here - let the profile error handle it
        setOAuthIntegrationsError('Authentication required. Please refresh the page or log in again.')
        return
      }
      if (Array.isArray(errorDetail)) {
        setOAuthIntegrationsError(errorDetail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(', '))
      } else if (typeof errorDetail === 'string') {
        setOAuthIntegrationsError(errorDetail)
      } else {
        setOAuthIntegrationsError(err.response?.data?.message || err.message || 'Failed to load OAuth integrations')
      }
    } finally {
      setOAuthIntegrationsLoading(false)
    }
  }

  const handleAuthorizeOAuth = async (integrationId: string) => {
    try {
      // Store current URL in sessionStorage before redirect (in case token is lost)
      sessionStorage.setItem('oauth_redirect_back', '/settings/profile')
      sessionStorage.setItem('oauth_integration_id', integrationId)
      
      const response = await integrationsApi.mcp.authorize(integrationId)
      // Redirect to OAuth authorization URL
      if (response.data.authorization_url) {
        window.location.href = response.data.authorization_url
      } else {
        setOAuthIntegrationsError('No authorization URL received')
      }
    } catch (error: any) {
      console.error('OAuth authorization failed:', error.response?.data?.detail || error.message)
      setOAuthIntegrationsError(`OAuth authorization failed: ${error.response?.data?.detail || error.message}`)
      // Clean up sessionStorage on error
      sessionStorage.removeItem('oauth_redirect_back')
      sessionStorage.removeItem('oauth_integration_id')
    }
  }

  const handleRevokeOAuth = async (integrationId: string) => {
    try {
      await integrationsApi.mcp.revoke(integrationId)
      setOAuthIntegrationsSuccess('OAuth authorization revoked successfully')
      // Reload integrations to reflect the change
      loadOAuthIntegrations()
    } catch (error: any) {
      console.error('OAuth revocation failed:', error.response?.data?.detail || error.message)
      setOAuthIntegrationsError(`OAuth revocation failed: ${error.response?.data?.detail || error.message}`)
    }
  }

  const loadEmailIntegrations = async () => {
    try {
      setEmailIntegrationsLoading(true)
      setEmailIntegrationsError(null)
      const response = await integrationsApi.email.listIntegrations('google')
      setEmailIntegrations(response.data.integrations || [])
    } catch (err: any) {
      const errorDetail = err.response?.data?.detail
      if (err.response?.status === 401 || (typeof errorDetail === 'string' && errorDetail.includes('Authorization header missing'))) {
        setEmailIntegrationsError('Authentication required. Please refresh the page or log in again.')
        return
      }
      if (Array.isArray(errorDetail)) {
        setEmailIntegrationsError(errorDetail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(', '))
      } else if (typeof errorDetail === 'string') {
        setEmailIntegrationsError(errorDetail)
      } else {
        setEmailIntegrationsError(err.response?.data?.message || err.message || 'Failed to load email integrations')
      }
    } finally {
      setEmailIntegrationsLoading(false)
    }
  }

  const loadCalendarIntegrations = async () => {
    try {
      setCalendarIntegrationsLoading(true)
      setCalendarIntegrationsError(null)
      const response = await integrationsApi.calendar.listIntegrations('google')
      setCalendarIntegrations(response.data.integrations || [])
    } catch (err: any) {
      const errorDetail = err.response?.data?.detail
      if (err.response?.status === 401 || (typeof errorDetail === 'string' && errorDetail.includes('Authorization header missing'))) {
        setCalendarIntegrationsError('Authentication required. Please refresh the page or log in again.')
        return
      }
      if (Array.isArray(errorDetail)) {
        setCalendarIntegrationsError(errorDetail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(', '))
      } else if (typeof errorDetail === 'string') {
        setCalendarIntegrationsError(errorDetail)
      } else {
        setCalendarIntegrationsError(err.response?.data?.message || err.message || 'Failed to load calendar integrations')
      }
    } finally {
      setCalendarIntegrationsLoading(false)
    }
  }

  const handleAuthorizeEmail = async (integrationId?: string) => {
    try {
      // Store current URL in sessionStorage before redirect (in case token is lost)
      sessionStorage.setItem('oauth_redirect_back', '/settings/profile')
      
      const response = await integrationsApi.email.authorize(integrationId, false) // false = user integration, not service
      // Redirect to OAuth authorization URL
      if (response.data.authorization_url) {
        window.location.href = response.data.authorization_url
      } else {
        setEmailIntegrationsError('No authorization URL received')
      }
    } catch (error: any) {
      console.error('Email OAuth authorization failed:', error.response?.data?.detail || error.message)
      setEmailIntegrationsError(`OAuth authorization failed: ${error.response?.data?.detail || error.message}`)
      sessionStorage.removeItem('oauth_redirect_back')
    }
  }

  const handleAuthorizeCalendar = async (integrationId?: string) => {
    try {
      // Store current URL in sessionStorage before redirect (in case token is lost)
      sessionStorage.setItem('oauth_redirect_back', '/settings/profile')
      
      const response = await integrationsApi.calendar.authorize(integrationId, false) // false = user integration, not service
      // Redirect to OAuth authorization URL
      if (response.data.authorization_url) {
        window.location.href = response.data.authorization_url
      } else {
        setCalendarIntegrationsError('No authorization URL received')
      }
    } catch (error: any) {
      console.error('Calendar OAuth authorization failed:', error.response?.data?.detail || error.message)
      setCalendarIntegrationsError(`OAuth authorization failed: ${error.response?.data?.detail || error.message}`)
      sessionStorage.removeItem('oauth_redirect_back')
    }
  }

  const handleDeleteEmailIntegration = async (integrationId: string) => {
    if (!confirm('Are you sure you want to delete this email integration?')) {
      return
    }
    try {
      await integrationsApi.email.deleteIntegration(integrationId)
      setEmailIntegrationsSuccess('Email integration deleted successfully')
      loadEmailIntegrations()
    } catch (error: any) {
      console.error('Delete email integration failed:', error.response?.data?.detail || error.message)
      setEmailIntegrationsError(`Failed to delete email integration: ${error.response?.data?.detail || error.message}`)
    }
  }

  const handleDeleteCalendarIntegration = async (integrationId: string) => {
    if (!confirm('Are you sure you want to delete this calendar integration?')) {
      return
    }
    try {
      await integrationsApi.calendar.deleteIntegration(integrationId)
      setCalendarIntegrationsSuccess('Calendar integration deleted successfully')
      loadCalendarIntegrations()
    } catch (error: any) {
      console.error('Delete calendar integration failed:', error.response?.data?.detail || error.message)
      setCalendarIntegrationsError(`Failed to delete calendar integration: ${error.response?.data?.detail || error.message}`)
    }
  }

  const handleUpdateBackgroundServices = async (e: React.FormEvent) => {
    e.preventDefault()
    setBackgroundServicesError(null)
    setBackgroundServicesSuccess(null)

    try {
      setBackgroundServicesSaving(true)
      await usersApi.updateBackgroundServicesPreferences({
        email_notifications_enabled: backgroundServicesData.email_notifications_enabled,
        calendar_notifications_enabled: backgroundServicesData.calendar_notifications_enabled,
      })
      setBackgroundServicesSuccess('Background services preferences updated successfully')
    } catch (err: any) {
      const errorDetail = err.response?.data?.detail
      if (Array.isArray(errorDetail)) {
        setBackgroundServicesError(errorDetail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(', '))
      } else if (typeof errorDetail === 'string') {
        setBackgroundServicesError(errorDetail)
      } else {
        setBackgroundServicesError(err.response?.data?.message || err.message || 'Failed to update background services preferences')
      }
    } finally {
      setBackgroundServicesSaving(false)
    }
  }

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault()
    setProfileError(null)
    setProfileSuccess(null)

    try {
      setProfileSaving(true)
      await usersApi.updateProfile({
        name: profileData.name || undefined,
        timezone: profileData.timezone || undefined,
      })
      setProfileSuccess('Profile updated successfully')
      // Update auth context if needed
      if (user) {
        // Trigger a refresh of user data
        window.location.reload()
      }
    } catch (err: any) {
      const errorDetail = err.response?.data?.detail
      if (Array.isArray(errorDetail)) {
        // Pydantic validation errors
        setProfileError(errorDetail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(', '))
      } else if (typeof errorDetail === 'string') {
        setProfileError(errorDetail)
      } else {
        setProfileError(err.response?.data?.message || err.message || 'Failed to update profile')
      }
    } finally {
      setProfileSaving(false)
    }
  }

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccess(null)

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }

    try {
      setLoading(true)
      await authApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      })
      setSuccess('Password changed successfully')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err: any) {
      const errorDetail = err.response?.data?.detail
      if (Array.isArray(errorDetail)) {
        // Pydantic validation errors
        setError(errorDetail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(', '))
      } else if (typeof errorDetail === 'string') {
        setError(errorDetail)
      } else {
        setError(err.response?.data?.message || err.message || 'Failed to change password')
      }
    } finally {
      setLoading(false)
    }
  }

  if (!user) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">Loading...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-2xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-4xl font-bold">Profile Settings</h1>
          <a
            href="/"
            className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400"
          >
            Home
          </a>
        </div>

        {/* User Info */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-semibold">User Information</h2>
            <Link
              href="/settings/tools"
              className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 underline"
            >
              Manage Tools
            </Link>
          </div>
          <dl className="space-y-3">
            <div>
              <dt className="text-sm font-medium text-gray-500 dark:text-gray-400">Email</dt>
              <dd className="mt-1 text-sm text-gray-900 dark:text-white">{user.email}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500 dark:text-gray-400">Role</dt>
              <dd className="mt-1">
                <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                  user.role === 'admin' 
                    ? 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
                    : user.role === 'viewer'
                    ? 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
                    : 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
                }`}>
                  {user.role}
                </span>
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500 dark:text-gray-400">Email Verified</dt>
              <dd className="mt-1 text-sm text-gray-900 dark:text-white">
                {user.email_verified ? (
                  <span className="text-green-600 dark:text-green-400">✓ Verified</span>
                ) : (
                  <span className="text-yellow-600 dark:text-yellow-400">⚠ Not verified</span>
                )}
              </dd>
            </div>
          </dl>
        </div>

        {/* Profile Settings */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6">
          <h2 className="text-2xl font-semibold mb-4">Profile Settings</h2>

          {profileError && (
            <div className="mb-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
              <p className="text-red-800 dark:text-red-200">{profileError}</p>
            </div>
          )}

          {profileSuccess && (
            <div className="mb-4 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
              <p className="text-green-800 dark:text-green-200">{profileSuccess}</p>
            </div>
          )}

          {profileLoading ? (
            <div className="text-sm text-gray-500">Loading profile...</div>
          ) : (
            <form onSubmit={handleUpdateProfile} className="space-y-4">
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Name
                </label>
                <input
                  id="name"
                  type="text"
                  value={profileData.name || ''}
                  onChange={(e) => setProfileData({ ...profileData, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  placeholder="Your name"
                />
              </div>

              <div>
                <label htmlFor="timezone" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Timezone
                </label>
                <select
                  id="timezone"
                  value={profileData.timezone || 'UTC'}
                  onChange={(e) => setProfileData({ ...profileData, timezone: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                >
                  {TIMEZONES.map((tz) => (
                    <option key={tz.value} value={tz.value}>
                      {tz.label}
                    </option>
                  ))}
                </select>
              </div>

              <button
                type="submit"
                disabled={profileSaving}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {profileSaving ? 'Saving...' : 'Save Profile'}
              </button>
            </form>
          )}
        </div>

        {/* Background Services Preferences */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6">
          <h2 className="text-2xl font-semibold mb-4">Background Services</h2>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            Control whether you receive proactive notifications from background services (email polling, calendar watching).
            These services run automatically and create notifications independently of tool preferences.
          </p>

          {backgroundServicesError && (
            <div className="mb-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
              <p className="text-red-800 dark:text-red-200">{backgroundServicesError}</p>
            </div>
          )}

          {backgroundServicesSuccess && (
            <div className="mb-4 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
              <p className="text-green-800 dark:text-green-200">{backgroundServicesSuccess}</p>
            </div>
          )}

          {backgroundServicesLoading ? (
            <div className="text-sm text-gray-500">Loading preferences...</div>
          ) : (
            <form onSubmit={handleUpdateBackgroundServices} className="space-y-4">
              <div className="flex items-center justify-between p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
                <div className="flex-1">
                  <label htmlFor="email_notifications" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Email Notifications
                  </label>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Receive notifications when new emails arrive in your Gmail account
                  </p>
                </div>
                <input
                  id="email_notifications"
                  type="checkbox"
                  checked={backgroundServicesData.email_notifications_enabled}
                  onChange={(e) => setBackgroundServicesData({ ...backgroundServicesData, email_notifications_enabled: e.target.checked })}
                  className="h-5 w-5 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
              </div>

              <div className="flex items-center justify-between p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
                <div className="flex-1">
                  <label htmlFor="calendar_notifications" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Calendar Notifications
                  </label>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Receive notifications for upcoming calendar events
                  </p>
                </div>
                <input
                  id="calendar_notifications"
                  type="checkbox"
                  checked={backgroundServicesData.calendar_notifications_enabled}
                  onChange={(e) => setBackgroundServicesData({ ...backgroundServicesData, calendar_notifications_enabled: e.target.checked })}
                  className="h-5 w-5 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
              </div>

              <button
                type="submit"
                disabled={backgroundServicesSaving}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {backgroundServicesSaving ? 'Saving...' : 'Save Preferences'}
              </button>
            </form>
          )}
        </div>

        {/* Email & Calendar Integrations */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6">
          <h2 className="text-2xl font-semibold mb-4">Email & Calendar Integrations</h2>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            Connect your personal Gmail and Google Calendar accounts to receive notifications and access your data.
            Each user can connect multiple accounts independently.
          </p>

          {/* Email Integrations */}
          <div className="mb-6">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white">Gmail Accounts</h3>
              <button
                onClick={() => handleAuthorizeEmail()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2 text-sm"
              >
                <ExternalLink size={16} />
                Connect Gmail
              </button>
            </div>

            {emailIntegrationsError && (
              <div className="mb-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                <p className="text-red-800 dark:text-red-200">{emailIntegrationsError}</p>
              </div>
            )}

            {emailIntegrationsSuccess && (
              <div className="mb-4 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
                <p className="text-green-800 dark:text-green-200">{emailIntegrationsSuccess}</p>
              </div>
            )}

            {emailIntegrationsLoading ? (
              <div className="text-sm text-gray-500">Loading email integrations...</div>
            ) : emailIntegrations.length === 0 ? (
              <div className="text-sm text-gray-500 p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
                No Gmail accounts connected. Click "Connect Gmail" to add your first account.
              </div>
            ) : (
              <div className="space-y-3">
                {emailIntegrations.map((integration) => (
                  <div
                    key={integration.id}
                    className="flex items-center justify-between p-4 border border-gray-200 dark:border-gray-700 rounded-lg"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className="text-sm font-medium text-gray-900 dark:text-white">
                          Gmail ({integration.provider})
                        </h4>
                        {integration.enabled ? (
                          <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
                            <CheckCircle size={14} />
                            Enabled
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
                            <XCircle size={14} />
                            Disabled
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        ID: {integration.id.substring(0, 8)}...
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleAuthorizeEmail(integration.id)}
                        className="px-3 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 flex items-center gap-2 text-xs"
                        title="Re-authenticate this Gmail account"
                      >
                        <ExternalLink size={14} />
                        Re-authorize
                      </button>
                      <button
                        onClick={() => handleDeleteEmailIntegration(integration.id)}
                        className="px-3 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 flex items-center gap-2 text-xs"
                        title="Delete this Gmail integration"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Calendar Integrations */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white">Google Calendar Accounts</h3>
              <button
                onClick={() => handleAuthorizeCalendar()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2 text-sm"
              >
                <ExternalLink size={16} />
                Connect Calendar
              </button>
            </div>

            {calendarIntegrationsError && (
              <div className="mb-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                <p className="text-red-800 dark:text-red-200">{calendarIntegrationsError}</p>
              </div>
            )}

            {calendarIntegrationsSuccess && (
              <div className="mb-4 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
                <p className="text-green-800 dark:text-green-200">{calendarIntegrationsSuccess}</p>
              </div>
            )}

            {calendarIntegrationsLoading ? (
              <div className="text-sm text-gray-500">Loading calendar integrations...</div>
            ) : calendarIntegrations.length === 0 ? (
              <div className="text-sm text-gray-500 p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
                No Google Calendar accounts connected. Click "Connect Calendar" to add your first account.
              </div>
            ) : (
              <div className="space-y-3">
                {calendarIntegrations.map((integration) => (
                  <div
                    key={integration.id}
                    className="flex items-center justify-between p-4 border border-gray-200 dark:border-gray-700 rounded-lg"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className="text-sm font-medium text-gray-900 dark:text-white">
                          Google Calendar ({integration.provider})
                        </h4>
                        {integration.enabled ? (
                          <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
                            <CheckCircle size={14} />
                            Enabled
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
                            <XCircle size={14} />
                            Disabled
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        ID: {integration.id.substring(0, 8)}...
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleAuthorizeCalendar(integration.id)}
                        className="px-3 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 flex items-center gap-2 text-xs"
                        title="Re-authenticate this Google Calendar account"
                      >
                        <ExternalLink size={14} />
                        Re-authorize
                      </button>
                      <button
                        onClick={() => handleDeleteCalendarIntegration(integration.id)}
                        className="px-3 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 flex items-center gap-2 text-xs"
                        title="Delete this Google Calendar integration"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* OAuth Authorizations */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6">
          <h2 className="text-2xl font-semibold mb-4">OAuth Authorizations</h2>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            Authorize your Google account to access Google Workspace services (Drive, Calendar, Gmail, etc.).
            Each user must authorize their own account separately.
          </p>

          {oauthIntegrationsError && (
            <div className="mb-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
              <p className="text-red-800 dark:text-red-200">{oauthIntegrationsError}</p>
            </div>
          )}

          {oauthIntegrationsLoading ? (
            <div className="text-sm text-gray-500">Loading OAuth integrations...</div>
          ) : oauthIntegrations.length === 0 ? (
            <div className="text-sm text-gray-500">
              No OAuth integrations found. If you expect to see Google Workspace integrations here, 
              please ensure that an admin has configured the Google Workspace MCP server in the 
              <Link href="/integrations" className="text-blue-600 dark:text-blue-400 hover:underline ml-1">
                Integrations
              </Link> page.
            </div>
          ) : (
            <div className="space-y-3">
              {oauthIntegrations.map((integration) => (
                <div
                  key={integration.integration_id}
                  className="flex items-center justify-between p-4 border border-gray-200 dark:border-gray-700 rounded-lg"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="text-sm font-medium text-gray-900 dark:text-white">
                        {integration.integration_name}
                      </h3>
                      {integration.oauth_authorized ? (
                        <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
                          <CheckCircle size={14} />
                          Authorized
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-xs text-yellow-600 dark:text-yellow-400">
                          <XCircle size={14} />
                          Not Authorized
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {integration.server_url}
                    </p>
                    {integration.oauth_authorized && integration.google_email && (
                      <p className="text-xs text-gray-600 dark:text-gray-300 mt-1">
                        Authorized as: <span className="font-medium">{integration.google_email}</span>
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {integration.oauth_authorized && (
                      <button
                        onClick={() => handleRevokeOAuth(integration.integration_id)}
                        className="px-3 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 flex items-center gap-2 text-xs"
                        title="Revoke OAuth authorization"
                      >
                        Revoke
                      </button>
                    )}
                    <button
                      onClick={() => handleAuthorizeOAuth(integration.integration_id)}
                      className={`px-4 py-2 rounded-lg flex items-center gap-2 text-sm ${
                        integration.oauth_authorized
                          ? 'bg-yellow-600 text-white hover:bg-yellow-700'
                          : 'bg-blue-600 text-white hover:bg-blue-700'
                      }`}
                      title={integration.oauth_authorized ? 'Re-authenticate to update permissions or switch account' : 'Authorize Google account access'}
                    >
                      <ExternalLink size={16} />
                      {integration.oauth_authorized ? 'Re-authorize' : 'Authorize'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Change Password */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h2 className="text-2xl font-semibold mb-4">Change Password</h2>

          {error && (
            <div className="mb-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
              <p className="text-red-800 dark:text-red-200">{error}</p>
            </div>
          )}

          {success && (
            <div className="mb-4 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
              <p className="text-green-800 dark:text-green-200">{success}</p>
            </div>
          )}

          <form onSubmit={handleChangePassword} className="space-y-4">
            <div>
              <label htmlFor="currentPassword" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Current Password *
              </label>
              <input
                id="currentPassword"
                type="password"
                required
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
            </div>

            <div>
              <label htmlFor="newPassword" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                New Password *
              </label>
              <input
                id="newPassword"
                type="password"
                required
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="Min 8 characters"
              />
            </div>

            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Confirm New Password *
              </label>
              <input
                id="confirmPassword"
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Changing...' : 'Change Password'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}

export default function ProfilePage() {
  return (
    <ProtectedRoute>
      <ProfileContent />
    </ProtectedRoute>
  )
}

