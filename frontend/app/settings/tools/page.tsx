'use client'

import { useRouter } from 'next/navigation'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import ToolsPreferences from '@/components/ToolsPreferences'

export default function ToolsPreferencesPage() {
  const router = useRouter()
  
  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-4xl mx-auto">
          <div className="mb-6">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold text-gray-900">Tools Preferences</h1>
                <p className="mt-2 text-gray-600">
                  Select which tools you want to enable for your AI assistant
                </p>
              </div>
              <a
                href="/"
                className="px-4 py-2 text-gray-700 hover:text-gray-900 underline"
              >
                Home
              </a>
            </div>
          </div>
          <ToolsPreferences 
            showHeader={false}
            showCancelButton={true}
            onClose={() => router.push('/settings/profile')}
          />
        </div>
      </div>
    </ProtectedRoute>
  )
}

