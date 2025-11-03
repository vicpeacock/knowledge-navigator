'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { integrationsApi } from '@/lib/api'
import { Calendar, CheckCircle, XCircle, RefreshCw, ExternalLink, Mail, ArrowLeft, Trash2 } from 'lucide-react'

interface Integration {
  id: string
  provider: string
  enabled: boolean
}

export default function IntegrationsPage() {
  const [calendarIntegrations, setCalendarIntegrations] = useState<Integration[]>([])
  const [emailIntegrations, setEmailIntegrations] = useState<Integration[]>([])
  const [loading, setLoading] = useState(true)
  const [connectingCalendar, setConnectingCalendar] = useState(false)
  const [connectingEmail, setConnectingEmail] = useState(false)

  useEffect(() => {
    loadIntegrations()
    // Check if we're returning from OAuth callback
    const urlParams = new URLSearchParams(window.location.search)
    if (urlParams.get('success') === 'true') {
      const integrationType = urlParams.get('type') || 'calendario'
      alert(`${integrationType === 'email' ? 'Gmail' : 'Calendario'} collegato con successo!`)
      // Clean URL
      window.history.replaceState({}, document.title, '/integrations')
    }
  }, [])

  const loadIntegrations = async () => {
    try {
      const [calendarResponse, emailResponse] = await Promise.all([
        integrationsApi.calendar.listIntegrations(),
        integrationsApi.email.listIntegrations(),
      ])
      setCalendarIntegrations(calendarResponse.data.integrations || [])
      setEmailIntegrations(emailResponse.data.integrations || [])
    } catch (error) {
      console.error('Error loading integrations:', error)
    } finally {
      setLoading(false)
    }
  }

  const connectGoogleCalendar = async () => {
    setConnectingCalendar(true)
    try {
      const response = await integrationsApi.calendar.authorize()
      if (response.data?.authorization_url) {
        window.location.href = response.data.authorization_url
      } else {
        throw new Error('No authorization URL received')
      }
    } catch (error: any) {
      console.error('Error connecting Google Calendar:', error)
      alert(`Errore nella connessione: ${error.response?.data?.detail || error.message}`)
      setConnectingCalendar(false)
    }
  }

  const connectGmail = async () => {
    setConnectingEmail(true)
    try {
      const response = await integrationsApi.email.authorize()
      if (response.data?.authorization_url) {
        window.location.href = response.data.authorization_url
      } else {
        throw new Error('No authorization URL received')
      }
    } catch (error: any) {
      console.error('Error connecting Gmail:', error)
      alert(`Errore nella connessione: ${error.response?.data?.detail || error.message}`)
      setConnectingEmail(false)
    }
  }

  const testGmailConnection = async () => {
    try {
      const gmailIntegration = emailIntegrations.find(
        (i) => i.provider === 'google' && i.enabled
      )
      
      if (!gmailIntegration) {
        alert('Nessuna integrazione Gmail trovata')
        return
      }

      const response = await integrationsApi.email.summarize(gmailIntegration.id, 3)
      
      if (response.data?.summary) {
        alert(`Riepilogo email non lette:\n\n${response.data.summary.substring(0, 500)}...`)
      } else {
        alert('Connessione funzionante!')
      }
    } catch (error: any) {
      console.error('Error testing Gmail:', error)
      alert(`Errore nel test: ${error.response?.data?.detail || error.message}`)
    }
  }

  const disconnectCalendar = async (integrationId: string) => {
    if (!integrationId) {
      alert('Nessuna integrazione trovata')
      return
    }
    
    if (!confirm('Sei sicuro di voler rimuovere questa integrazione del calendario?')) {
      return
    }
    
    try {
      await integrationsApi.calendar.deleteIntegration(integrationId)
      alert('Integrazione rimossa con successo')
      loadIntegrations()
    } catch (error: any) {
      console.error('Error disconnecting calendar:', error)
      alert(`Errore nella rimozione: ${error.response?.data?.detail || error.message}`)
    }
  }

  const disconnectEmail = async (integrationId: string) => {
    if (!integrationId) {
      alert('Nessuna integrazione trovata')
      return
    }
    
    if (!confirm('Sei sicuro di voler rimuovere questa integrazione email?')) {
      return
    }
    
    try {
      await integrationsApi.email.deleteIntegration(integrationId)
      alert('Integrazione rimossa con successo')
      loadIntegrations()
    } catch (error: any) {
      console.error('Error disconnecting email:', error)
      alert(`Errore nella rimozione: ${error.response?.data?.detail || error.message}`)
    }
  }

  const testCalendarConnection = async () => {
    try {
      // Get first enabled Google Calendar integration
      const googleIntegration = calendarIntegrations.find(
        (i) => i.provider === 'google' && i.enabled
      )
      
      if (!googleIntegration) {
        alert('Nessuna integrazione Google Calendar trovata')
        return
      }

      // Test query for today's events
      const response = await integrationsApi.calendar.query(
        'eventi oggi',
        'google',
        googleIntegration.id
      )
      
      if (response.data?.events) {
        const count = response.data.count || 0
        alert(`Connessione funzionante! Trovati ${count} eventi oggi.`)
      } else {
        alert('Connessione funzionante, ma nessun evento trovato.')
      }
    } catch (error: any) {
      console.error('Error testing calendar:', error)
      alert(`Errore nel test: ${error.response?.data?.detail || error.message}`)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">Caricamento...</div>
      </div>
    )
  }

  const hasGoogleCalendar = calendarIntegrations.some(
    (i) => i.provider === 'google' && i.enabled
  )

  return (
    <div className="min-h-screen p-8 bg-gray-50 dark:bg-gray-900">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 mb-4 transition-colors"
          >
            <ArrowLeft size={20} />
            <span>Torna alla Home</span>
          </Link>
          <h1 className="text-4xl font-bold mb-2">Integrazioni</h1>
          <p className="text-gray-600 dark:text-gray-400">
            Collega i tuoi servizi esterni per arricchire il Knowledge Navigator
          </p>
        </div>

        {/* Google Calendar Section */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 mb-6">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <Calendar size={32} className="text-blue-600" />
              <div>
                <h2 className="text-2xl font-semibold">Google Calendar</h2>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Accedi ai tuoi eventi e appuntamenti
                </p>
              </div>
            </div>
            {hasGoogleCalendar ? (
              <div className="flex items-center gap-2 text-green-600">
                <CheckCircle size={24} />
                <span className="font-semibold">Collegato</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-gray-400">
                <XCircle size={24} />
                <span>Non collegato</span>
              </div>
            )}
          </div>

          {hasGoogleCalendar ? (
            <div className="space-y-4">
              <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
                <p className="text-sm text-green-800 dark:text-green-200">
                  ✓ Google Calendar è collegato e funzionante. Puoi chiedere al chatbot informazioni
                  sul tuo calendario con domande come:
                </p>
                <ul className="mt-2 ml-4 list-disc text-sm text-green-700 dark:text-green-300">
                  <li>&ldquo;Ho eventi domani?&rdquo;</li>
                  <li>&ldquo;Quali meeting ho questa settimana?&rdquo;</li>
                  <li>&ldquo;Mostrami gli appuntamenti di oggi&rdquo;</li>
                </ul>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={testCalendarConnection}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"
                >
                  <RefreshCw size={18} />
                  Test Connessione
                </button>
                {calendarIntegrations.find(i => i.provider === 'google' && i.enabled) && (
                  <button
                    onClick={() => {
                      const integration = calendarIntegrations.find(i => i.provider === 'google' && i.enabled)
                      if (integration?.id) {
                        disconnectCalendar(integration.id)
                      } else {
                        alert('Nessuna integrazione trovata')
                      }
                    }}
                    className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 flex items-center gap-2"
                  >
                    <Trash2 size={18} />
                    Rimuovi
                  </button>
                )}
                <button
                  onClick={loadIntegrations}
                  className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-white rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600"
                >
                  Aggiorna
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg">
                <p className="text-sm text-yellow-800 dark:text-yellow-200">
                  Per collegare Google Calendar, clicca il pulsante qui sotto. Verrai reindirizzato a
                  Google per autorizzare l&apos;accesso al tuo calendario.
                </p>
              </div>
              <button
                onClick={connectGoogleCalendar}
                disabled={connectingCalendar}
                className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {connectingCalendar ? (
                  <>
                    <RefreshCw size={18} className="animate-spin" />
                    Connessione in corso...
                  </>
                ) : (
                  <>
                    <ExternalLink size={18} />
                    Connetti Google Calendar
                  </>
                )}
              </button>
            </div>
          )}
        </div>

        {/* Gmail Section */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 mb-6">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <Mail size={32} className="text-red-600" />
              <div>
                <h2 className="text-2xl font-semibold">Gmail</h2>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Accedi alle tue email e riassunti automatici
                </p>
              </div>
            </div>
            {emailIntegrations.some((i) => i.provider === 'google' && i.enabled) ? (
              <div className="flex items-center gap-2 text-green-600">
                <CheckCircle size={24} />
                <span className="font-semibold">Collegato</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-gray-400">
                <XCircle size={24} />
                <span>Non collegato</span>
              </div>
            )}
          </div>

          {emailIntegrations.some((i) => i.provider === 'google' && i.enabled) ? (
            <div className="space-y-4">
              <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
                <p className="text-sm text-green-800 dark:text-green-200">
                  ✓ Gmail è collegato e funzionante. Puoi chiedere al chatbot di:
                </p>
                <ul className="mt-2 ml-4 list-disc text-sm text-green-700 dark:text-green-300">
                  <li>Riassumere le email non lette</li>
                  <li>Cercare email per mittente o argomento</li>
                  <li>Ottenere informazioni sulle email recenti</li>
                </ul>
              </div>
                  <div className="flex gap-3">
                    <button
                      onClick={testGmailConnection}
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"
                    >
                      <RefreshCw size={18} />
                      Test Connessione
                    </button>
                    {emailIntegrations.find(i => i.provider === 'google' && i.enabled) && (
                      <button
                        onClick={() => {
                          const integration = emailIntegrations.find(i => i.provider === 'google' && i.enabled)
                          if (integration?.id) {
                            disconnectEmail(integration.id)
                          } else {
                            alert('Nessuna integrazione trovata')
                          }
                        }}
                        className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 flex items-center gap-2"
                      >
                        <Trash2 size={18} />
                        Rimuovi
                      </button>
                    )}
                    <button
                      onClick={loadIntegrations}
                      className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-white rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600"
                    >
                      Aggiorna
                    </button>
                  </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg">
                <p className="text-sm text-yellow-800 dark:text-yellow-200">
                  Per collegare Gmail, clicca il pulsante qui sotto. Verrai reindirizzato a
                  Google per autorizzare l&apos;accesso alla tua casella email.
                </p>
              </div>
              <button
                onClick={connectGmail}
                disabled={connectingEmail}
                className="px-6 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {connectingEmail ? (
                  <>
                    <RefreshCw size={18} className="animate-spin" />
                    Connessione in corso...
                  </>
                ) : (
                  <>
                    <ExternalLink size={18} />
                    Connetti Gmail
                  </>
                )}
              </button>
            </div>
          )}
        </div>

        {/* Info Section */}
        <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-6">
          <h3 className="font-semibold mb-2 text-blue-900 dark:text-blue-100">
            Come funziona?
          </h3>
          <ul className="space-y-2 text-sm text-blue-800 dark:text-blue-200">
            <li>
                  • Le credenziali sono criptate e salvate in modo sicuro nel database
            </li>
            <li>
              • Puoi chiedere al chatbot informazioni sul calendario in linguaggio naturale
            </li>
            <li>
              • Il sistema riconosce automaticamente quando una domanda riguarda il calendario
            </li>
            <li>
              • Supporto per query come &ldquo;eventi domani&rdquo;, &ldquo;meeting questa settimana&rdquo;, ecc.
            </li>
          </ul>
        </div>
      </div>
    </div>
  )
}

