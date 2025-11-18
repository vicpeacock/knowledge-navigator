'use client'

import { useEffect, useState, useRef } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { BarChart3, RefreshCw, Download, Home, FileText, FileDown } from 'lucide-react'
import api from '@/lib/api'

interface Metric {
  name: string
  type: string
  value: number
  labels?: Record<string, string>
}

function MetricsContent() {
  const { user, refreshToken } = useAuth()
  const router = useRouter()
  const [metrics, setMetrics] = useState<string>('')
  const [parsedMetrics, setParsedMetrics] = useState<Metric[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [evaluationLoading, setEvaluationLoading] = useState(false)
  const [evaluationReport, setEvaluationReport] = useState<string | null>(null)
  const [showEvaluationModal, setShowEvaluationModal] = useState(false)
  const [evaluationStatus, setEvaluationStatus] = useState<'idle' | 'generating' | 'completed' | 'failed'>('idle')
  const statusCheckIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const isPollingRef = useRef<boolean>(false)
  const pollingStartTimeRef = useRef<number | null>(null)

  useEffect(() => {
    if (user?.role !== 'admin') {
      router.push('/')
      return
    }
    loadMetrics()
    // Verifica lo stato iniziale dell'evaluation (solo una volta al mount)
    checkEvaluationStatus()
    
    return () => {
      // Cleanup: ferma il polling quando il componente viene smontato
      if (statusCheckIntervalRef.current) {
        clearInterval(statusCheckIntervalRef.current)
        statusCheckIntervalRef.current = null
      }
      isPollingRef.current = false
    }
  }, [user, router])

  const loadMetrics = async () => {
    try {
      setLoading(true)
      setError(null)
      // Usa fetch diretto per /metrics perché è un endpoint pubblico Prometheus
      // Non richiede autenticazione
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const response = await fetch(`${apiUrl}/metrics`, {
        method: 'GET',
        headers: {
          'Accept': 'text/plain',
        },
      })
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      const text = await response.text()
      setMetrics(text)
      parseMetrics(text)
    } catch (err: any) {
      console.error('Error loading metrics:', err)
      if (err.message?.includes('Failed to fetch') || err.message?.includes('NetworkError')) {
        setError('Network Error: Cannot connect to backend. Make sure the backend is running on port 8000.')
      } else {
        setError(err.message || 'Failed to load metrics')
      }
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

  const stopPolling = () => {
    if (statusCheckIntervalRef.current) {
      clearInterval(statusCheckIntervalRef.current)
      statusCheckIntervalRef.current = null
    }
    isPollingRef.current = false
    pollingStartTimeRef.current = null
  }

  const checkEvaluationStatus = async () => {
    // Timeout di sicurezza: ferma il polling dopo 20 minuti
    if (pollingStartTimeRef.current) {
      const elapsed = Date.now() - pollingStartTimeRef.current
      if (elapsed > 20 * 60 * 1000) { // 20 minuti
        console.warn('Polling timeout: stopping after 20 minutes')
        stopPolling()
        setEvaluationStatus('failed')
        setEvaluationLoading(false)
        setError('Evaluation timeout: stopped polling after 20 minutes')
        return
      }
    }

    try {
      const response = await api.get('/api/v1/evaluation/status', {
        timeout: 5000, // Timeout di 5 secondi per evitare richieste bloccanti
      })
      const status = response.data.status
      const hasReport = response.data.has_report
      
      if (status === 'running' || status === 'pending') {
        setEvaluationStatus('generating')
        setEvaluationLoading(true)
        // Avvia il polling solo se non è già attivo
        if (!isPollingRef.current) {
          isPollingRef.current = true
          pollingStartTimeRef.current = Date.now()
          // Usa un intervallo più lungo per ridurre le richieste: 5 secondi invece di 2
          const interval = setInterval(() => {
            checkEvaluationStatus()
          }, 5000) // Controlla ogni 5 secondi invece di 2
          statusCheckIntervalRef.current = interval
        }
      } else if (status === 'completed' && hasReport) {
        stopPolling()
        setEvaluationStatus('completed')
        setEvaluationLoading(false)
        // Carica il report se non è già caricato
        if (!evaluationReport) {
          loadEvaluationReport()
        }
      } else if (status === 'failed') {
        stopPolling()
        setEvaluationStatus('failed')
        setEvaluationLoading(false)
        setError(response.data.error || 'Evaluation failed')
      } else if (status === null && hasReport) {
        // C'è un report disponibile ma nessun job attivo
        stopPolling()
        setEvaluationStatus('completed')
        setEvaluationLoading(false)
        if (!evaluationReport) {
          loadEvaluationReport()
        }
      } else {
        // Status è null o idle - ferma il polling se era attivo
        if (isPollingRef.current) {
          stopPolling()
        }
        setEvaluationStatus('idle')
        setEvaluationLoading(false)
      }
    } catch (err: any) {
      console.error('Error checking evaluation status:', err)
      // Se c'è un errore di rete o timeout, ferma il polling dopo alcuni tentativi
      if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
        // Non fermare immediatamente, potrebbe essere un problema temporaneo
        // Ma limita il numero di retry
        if (pollingStartTimeRef.current) {
          const elapsed = Date.now() - pollingStartTimeRef.current
          if (elapsed > 5 * 60 * 1000) { // Dopo 5 minuti di errori, ferma
            stopPolling()
            setEvaluationStatus('failed')
            setEvaluationLoading(false)
            setError('Network timeout: unable to check evaluation status')
          }
        }
      } else if (err.response?.status === 404) {
        // Se c'è un errore 404, significa che non c'è nessun job
        stopPolling()
        setEvaluationStatus('idle')
        setEvaluationLoading(false)
      } else if (err.response?.status === 401) {
        // Token scaduto - ferma il polling e reindirizza al login
        stopPolling()
        setEvaluationStatus('failed')
        setEvaluationLoading(false)
        setError('Session expired. Please login again.')
        setTimeout(() => {
          router.push('/auth/login')
        }, 2000)
      }
    }
  }

  const loadEvaluationReport = async () => {
    try {
      const response = await api.get('/api/v1/evaluation/report', {
        responseType: 'text',
      })
      setEvaluationReport(response.data)
    } catch (err: any) {
      console.error('Error loading evaluation report:', err)
      if (err.response?.status !== 404) {
        setError('Failed to load evaluation report')
      }
    }
  }

  const generateEvaluationReport = async () => {
    // Se il report è già disponibile, mostra direttamente il modal
    if (evaluationReport && evaluationStatus === 'completed') {
      setShowEvaluationModal(true)
      return
    }
    
    // Se c'è già un polling attivo, non avviarne un altro
    if (isPollingRef.current) {
      console.warn('Evaluation already in progress')
      return
    }
    
    try {
      setEvaluationLoading(true)
      setEvaluationStatus('generating')
      setError(null)
      
      // Avvia la generazione asincrona
      await api.post('/api/v1/evaluation/start', {}, {
        params: {
          max_tests: 5, // Limita a 5 test cases per evitare timeout
        },
        timeout: 30000, // 30 secondi timeout per l'avvio
      })
      
      // Controlla immediatamente lo stato (questo avvierà il polling se necessario)
      checkEvaluationStatus()
    } catch (err: any) {
      console.error('Error starting evaluation report:', err)
      
      if (err.response?.status === 401) {
        // Token scaduto - prova a fare refresh
        try {
          await refreshToken()
          // Riprova dopo il refresh
          await api.post('/api/v1/evaluation/start', {}, {
            params: {
              max_tests: 5,
            },
            timeout: 30000,
          })
          checkEvaluationStatus()
          return
        } catch (refreshErr: any) {
          // Refresh fallito, reindirizza al login
          setError('Session expired. Please login again.')
          setTimeout(() => {
            router.push('/auth/login')
          }, 2000)
          return
        }
      }
      
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to start evaluation report'
      setError(errorMessage)
      setEvaluationStatus('failed')
      setEvaluationLoading(false)
    }
  }

  const stopEvaluationReport = async () => {
    try {
      await api.post('/api/v1/evaluation/stop', {}, {
        timeout: 10000, // 10 secondi timeout
      })
      stopPolling()
      setEvaluationStatus('idle')
      setEvaluationLoading(false)
      setError(null)
    } catch (err: any) {
      console.error('Error stopping evaluation report:', err)
      // Anche se c'è un errore, ferma comunque il polling locale
      stopPolling()
      setEvaluationStatus('idle')
      setEvaluationLoading(false)
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to stop evaluation report'
      setError(errorMessage)
    }
  }

  const downloadPDF = async () => {
    if (!evaluationReport) return
    
    try {
      // Dynamic import per evitare problemi SSR
      const html2pdf = (await import('html2pdf.js')).default
      
      // Crea un elemento temporaneo con il contenuto HTML
      // Estraiamo solo il body content dal report HTML completo
      const parser = new DOMParser()
      const doc = parser.parseFromString(evaluationReport, 'text/html')
      const bodyContent = doc.body || doc.documentElement
      
      // Crea un elemento wrapper per il PDF
      const element = document.createElement('div')
      element.innerHTML = bodyContent.innerHTML
      element.style.width = '210mm' // A4 width
      element.style.padding = '20mm'
      
      // Opzioni per html2pdf
      const opt = {
        margin: [10, 10, 10, 10],
        filename: `evaluation-report-${new Date().toISOString().split('T')[0]}.pdf`,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { 
          scale: 2, 
          useCORS: true,
          logging: false,
          letterRendering: true
        },
        jsPDF: { 
          unit: 'mm', 
          format: 'a4', 
          orientation: 'portrait' 
        },
        pagebreak: { 
          mode: ['avoid-all', 'css', 'legacy'],
          before: '.page-break-before',
          after: '.page-break-after',
          avoid: ['.test-result', '.summary-card']
        }
      }
      
      // Genera e scarica il PDF
      html2pdf().set(opt).from(element).save()
    } catch (err: any) {
      console.error('Error generating PDF:', err)
      setError('Failed to generate PDF. Please try again.')
    }
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
            {evaluationStatus === 'generating' ? (
              <>
                <button
                  onClick={stopEvaluationReport}
                  className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 flex items-center gap-2"
                  title="Stop evaluation report generation"
                >
                  <RefreshCw size={18} />
                  Stop
                </button>
                <button
                  disabled
                  className="px-4 py-2 bg-purple-600 text-white rounded-lg flex items-center gap-2 opacity-50 cursor-not-allowed"
                  title="Generating evaluation report..."
                >
                  <RefreshCw className="animate-spin" size={18} />
                  Generating...
                </button>
              </>
            ) : (
              <>
                {evaluationReport && evaluationStatus === 'completed' && (
                  <button
                    onClick={() => setShowEvaluationModal(true)}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center gap-2"
                    title="View evaluation report"
                  >
                    <FileText size={18} />
                    View Report
                  </button>
                )}
                <button
                  onClick={generateEvaluationReport}
                  disabled={evaluationLoading}
                  className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Generate evaluation report (may take 5-15 minutes)"
                >
                  <FileText size={18} />
                  Generate Report
                </button>
              </>
            )}
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

      {/* Evaluation Report Modal */}
      {showEvaluationModal && evaluationReport && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-6xl h-[90vh] flex flex-col">
            <div className="flex justify-between items-center p-4 border-b border-gray-200 dark:border-gray-700">
              <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">
                Agent Evaluation Report
              </h2>
              <div className="flex gap-2">
                <button
                  onClick={downloadPDF}
                  className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center gap-2"
                >
                  <FileDown size={18} />
                  Download PDF
                </button>
                <button
                  onClick={() => {
                    setShowEvaluationModal(false)
                    // Non rimuovere il report dalla cache, così può essere riaperto velocemente
                  }}
                  className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700"
                >
                  Close
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-auto p-4">
              <iframe
                srcDoc={evaluationReport}
                className="w-full h-full border-0"
                title="Evaluation Report"
              />
            </div>
          </div>
        </div>
      )}
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

