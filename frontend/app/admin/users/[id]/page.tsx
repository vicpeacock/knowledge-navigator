'use client'

import { useEffect, useState } from 'react'
import { useRouter, useParams } from 'next/navigation'
import Link from 'next/link'
import { usersApi } from '@/lib/api'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import type { UserResponse, UserUpdate } from '@/types/auth'

function EditUserContent() {
  const params = useParams()
  const userId = params.id as string
  const router = useRouter()
  
  const [user, setUser] = useState<UserResponse | null>(null)
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [role, setRole] = useState<'admin' | 'user' | 'viewer'>('user')
  const [active, setActive] = useState(true)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (userId) {
      loadUser()
    }
  }, [userId])

  const loadUser = async () => {
    try {
      setLoading(true)
      const response = await usersApi.get(userId)
      const userData = response.data
      setUser(userData)
      setEmail(userData.email || '')
      setName(userData.name || '')
      setRole(userData.role as 'admin' | 'user' | 'viewer')
      setActive(userData.active)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load user')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSaving(true)

    try {
      const updateData: UserUpdate = {
        email: email || undefined,
        name: name || undefined,
        role,
        active,
      }
      await usersApi.update(userId, updateData)
      router.push('/admin/users')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update user')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">Loading user...</div>
      </div>
    )
  }

  if (!user) {
    return (
      <div className="min-h-screen p-8">
        <div className="max-w-2xl mx-auto">
          <p className="text-red-600">User not found</p>
          <Link href="/admin/users" className="text-blue-600 hover:text-blue-700">
            ← Back to Users
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-2xl mx-auto">
        <div className="mb-8">
          <div className="flex justify-between items-center">
            <div>
              <Link
                href="/admin/users"
                className="text-blue-600 hover:text-blue-700 dark:text-blue-400"
              >
                ← Back to Users
              </Link>
              <h1 className="text-4xl font-bold mt-4">Edit User</h1>
            </div>
            <Link
              href="/"
              className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400"
            >
              Home
            </Link>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <p className="text-red-800 dark:text-red-200">{error}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            />
            <p className="mt-1 text-xs text-gray-500">
              You can change the email (must be unique within the tenant).
            </p>
          </div>

          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Name
            </label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            />
          </div>

          <div>
            <label htmlFor="role" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Role *
            </label>
            <select
              id="role"
              required
              value={role}
              onChange={(e) => setRole(e.target.value as 'admin' | 'user' | 'viewer')}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            >
              <option value="user">User</option>
              <option value="admin">Admin</option>
              <option value="viewer">Viewer</option>
            </select>
          </div>

          <div className="flex items-center">
            <input
              id="active"
              type="checkbox"
              checked={active}
              onChange={(e) => setActive(e.target.checked)}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
            />
            <label htmlFor="active" className="ml-2 block text-sm text-gray-900 dark:text-gray-300">
              Active
            </label>
          </div>

          <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">User Information:</p>
            <ul className="text-sm text-gray-500 dark:text-gray-400 space-y-1">
              <li>Created: {new Date(user.created_at).toLocaleString()}</li>
              <li>Last Login: {user.last_login_at ? new Date(user.last_login_at).toLocaleString() : 'Never'}</li>
              <li>Email Verified: {user.email_verified ? 'Yes' : 'No'}</li>
            </ul>
          </div>

          <div className="flex gap-4">
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
            <Link
              href="/admin/users"
              className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600"
            >
              Cancel
            </Link>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function EditUserPage() {
  return (
    <ProtectedRoute requireAdmin>
      <EditUserContent />
    </ProtectedRoute>
  )
}

