'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { BarChart3, RefreshCw, Download, Home } from 'lucide-react'

interface Metric {
  name: string
  type: string
  value: number
  labels?: Record<string, string>
}

function MetricsContent() {
  const { user } = useAuth()
  const router = useRouter()
  const [metrics, setMetrics] = useState<string>('')
  const [parsedMetrics, setParsedMetrics] = useState<Metric[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (user?.role !== 'admin') {
      router.push('/')
      return
    }
    loadMetrics()
  }, [user, router])

  const loadMetrics = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await fetch('http://localhost:8000/metrics')
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      const text = await response.text()
      setMetrics(text)
      parseMetrics(text)
    } catch (err: any) {
      console.error('Error loading metrics:', err)
      setError(err.message || 'Failed to load metrics')
    } finally {
      setLoading(false)
    }
  }

  const parseMetrics = (text: string) => {
    const lines = text.split('\n').filter(line => line.trim() && !line.startsWith('#'))
    const parsed: Metric[] = []
    
    for (const line of lines) {
      const match = line.match(/^([a-z_]+)(?:\{([^}]+)\})?\s+([0-9.]+)$/)
      if (match) {
        const [, name, labelsStr, value] = match
        const labels: Record<string, string> = {}
        
        if (labelsStr) {
          labelsStr.split(',').forEach(pair => {
            const [key, val] = pair.split('=')
            if (key && val) {
              labels[key.trim()] = val.trim().replace(/"/g, '')
            }
          })
        }
        
        parsed.push({
          name,
          type: 'counter', // Default, could be improved
          value: parseFloat(value),
          labels: Object.keys(labels).length > 0 ? labels : undefined
        })
      }
    }
    
    setParsedMetrics(parsed)
  }

  const downloadMetrics = () => {
    const blob = new Blob([metrics], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `metrics-${new Date().toISOString()}.txt`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const groupMetricsByName = () => {
    const grouped: Record<string, Metric[]> = {}
    parsedMetrics.forEach(metric => {
      if (!grouped[metric.name]) {
        grouped[metric.name] = []
      }
      grouped[metric.name].push(metric)
    })
    return grouped
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="animate-spin h-8 w-8 mx-auto mb-4" />
          <p>Loading metrics...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen p-8">
        <div className="max-w-4xl mx-auto">
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6">
            <h2 className="text-xl font-bold text-red-600 dark:text-red-400 mb-2">Error Loading Metrics</h2>
            <p className="text-red-700 dark:text-red-300">{error}</p>
            <button
              onClick={loadMetrics}
              className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    )
  }

  const grouped = groupMetricsByName()

  return (
    <div className="min-h-screen p-8 bg-gray-50 dark:bg-gray-900">
      <div className="max-w-6xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-3xl font-bold mb-2">Observability Metrics</h1>
            <p className="text-gray-600 dark:text-gray-400">
              Real-time metrics from Knowledge Navigator backend
            </p>
          </div>
          <div className="flex gap-3">
            <Link
              href="/"
              className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 flex items-center gap-2"
            >
              <Home size={18} />
              Home
            </Link>
            <button
              onClick={loadMetrics}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"
            >
              <RefreshCw size={18} />
              Refresh
            </button>
            <button
              onClick={downloadMetrics}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center gap-2"
            >
              <Download size={18} />
              Download
            </button>
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 className="text-blue-600" size={24} />
            <h2 className="text-xl font-semibold">Metrics Summary</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg">
              <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">Total Metrics</div>
              <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                {parsedMetrics.length}
              </div>
            </div>
            <div className="bg-green-50 dark:bg-green-900/20 p-4 rounded-lg">
              <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">Metric Types</div>
              <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                {Object.keys(grouped).length}
              </div>
            </div>
            <div className="bg-purple-50 dark:bg-purple-900/20 p-4 rounded-lg">
              <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">HTTP Requests</div>
              <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
                {parsedMetrics
                  .filter(m => m.name === 'http_requests_total')
                  .reduce((sum, m) => sum + m.value, 0)
                  .toFixed(0)}
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          {Object.entries(grouped).map(([name, metrics]) => (
            <div key={name} className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
                {name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 dark:border-gray-700">
                      <th className="text-left py-2 px-4 text-gray-700 dark:text-gray-300">Labels</th>
                      <th className="text-right py-2 px-4 text-gray-700 dark:text-gray-300">Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {metrics.map((metric, idx) => (
                      <tr key={idx} className="border-b border-gray-100 dark:border-gray-800">
                        <td className="py-2 px-4">
                          {metric.labels ? (
                            <div className="flex flex-wrap gap-2">
                              {Object.entries(metric.labels).map(([key, value]) => (
                                <span
                                  key={key}
                                  className="px-2 py-1 bg-gray-100 dark:bg-gray-700 rounded text-xs"
                                >
                                  {key}: {value}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-gray-400">(no labels)</span>
                          )}
                        </td>
                        <td className="text-right py-2 px-4 font-mono">
                          {metric.value.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-6 bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
            Raw Metrics (Prometheus Format)
          </h3>
          <pre className="bg-gray-50 dark:bg-gray-900 p-4 rounded overflow-auto text-xs font-mono">
            {metrics}
          </pre>
        </div>
      </div>
    </div>
  )
}

export default function MetricsPage() {
  return (
    <ProtectedRoute requireAdmin>
      <MetricsContent />
    </ProtectedRoute>
  )
}

