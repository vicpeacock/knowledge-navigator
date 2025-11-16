'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { usersApi } from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import type { UserResponse } from '@/types/auth'

function UsersListContent() {
  const [users, setUsers] = useState<UserResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState({ role: '', active: '' })
  const { user } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (user?.role !== 'admin') {
      router.push('/')
      return
    }
    loadUsers()
  }, [user, filters])

  const loadUsers = async () => {
    try {
      setLoading(true)
      const params: any = {}
      if (filters.role) params.role = filters.role
      if (filters.active !== '') params.active = filters.active === 'true'
      
      const response = await usersApi.list(params)
      setUsers(response.data || [])
      setError(null)
    } catch (err: any) {
      console.error('Error loading users:', err)
      setError(err.response?.data?.detail || 'Failed to load users')
      setUsers([])
    } finally {
      setLoading(false)
    }
  }

  const handleResendInvitation = async (userId: string) => {
    if (!confirm('Resend verification email to this user?')) {
      return
    }
    try {
      await usersApi.resendInvitation(userId)
      alert('Verification email sent (if SMTP is configured).')
    } catch (err: any) {
      console.error('Error resending invitation:', err)
      alert(err.response?.data?.detail || 'Failed to resend verification email')
    }
  }

  const handleDelete = async (userId: string) => {
    if (!confirm('Are you sure you want to deactivate this user?')) {
      return
    }

    try {
      await usersApi.delete(userId)
      loadUsers() // Reload list
    } catch (err: any) {
      alert(`Error: ${err.response?.data?.detail || 'Failed to deactivate user'}`)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">Loading users...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-4xl font-bold">User Management</h1>
            <div className="mt-2 flex gap-4 text-sm">
              <Link
                href="/"
                className="text-blue-600 hover:text-blue-700 dark:text-blue-400"
              >
                ← Home
              </Link>
            </div>
          </div>
          <Link
            href="/admin/users/new"
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Create New User
          </Link>
        </div>

        {error && (
          <div className="mb-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <p className="text-red-800 dark:text-red-200">{error}</p>
          </div>
        )}

        {/* Filters */}
        <div className="mb-6 flex gap-4">
          <select
            value={filters.role}
            onChange={(e) => setFilters({ ...filters, role: e.target.value })}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
          >
            <option value="">All Roles</option>
            <option value="admin">Admin</option>
            <option value="user">User</option>
            <option value="viewer">Viewer</option>
          </select>

          <select
            value={filters.active}
            onChange={(e) => setFilters({ ...filters, active: e.target.value })}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
          >
            <option value="">All Status</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
        </div>

        {/* Users Table */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-700">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Email
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Role
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Last Login
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                    {u.email}
                    {!u.email_verified && (
                      <span className="ml-2 text-xs text-yellow-600 dark:text-yellow-400">(unverified)</span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    {u.name || '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                      u.role === 'admin' 
                        ? 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
                        : u.role === 'viewer'
                        ? 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
                        : 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
                    }`}>
                      {u.role}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                      u.active
                        ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                        : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                    }`}>
                      {u.active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    {u.last_login_at 
                      ? new Date(u.last_login_at).toLocaleString()
                      : 'Never'
                    }
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <div className="flex flex-wrap gap-2">
                      <Link
                        href={`/admin/users/${u.id}`}
                        className="text-blue-600 hover:text-blue-900 dark:text-blue-400"
                      >
                        Edit
                      </Link>
                      {!u.email_verified && (
                        <button
                          onClick={() => handleResendInvitation(u.id)}
                          className="text-amber-600 hover:text-amber-800 dark:text-amber-400 text-sm"
                        >
                          Verify Email
                        </button>
                      )}
                      <button
                        onClick={() => handleDelete(u.id)}
                        className="text-red-600 hover:text-red-900 dark:text-red-400"
                      >
                        {u.active ? 'Deactivate' : 'Activate'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {users.length === 0 && (
            <div className="text-center py-12">
              <p className="text-gray-500 dark:text-gray-400">No users found</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function UsersListPage() {
  return (
    <ProtectedRoute requireAdmin>
      <UsersListContent />
    </ProtectedRoute>
  )
}

