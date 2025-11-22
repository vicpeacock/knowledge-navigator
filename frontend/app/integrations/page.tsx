'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { integrationsApi } from '@/lib/api'
import { Calendar, CheckCircle, XCircle, RefreshCw, ExternalLink, Mail, ArrowLeft, Trash2, Server, MessageSquare, RotateCcw, Edit2, Save, X } from 'lucide-react'
import { useStatus } from '@/components/StatusPanel'
import { useAuth } from '@/contexts/AuthContext'

interface Integration {
  id: string
  provider: string
  enabled: boolean
}

interface MCPIntegration extends Integration {
  name: string
  server_url: string
  selected_tools: string[]
  oauth_required?: boolean
}

export default function IntegrationsPage() {
  const [calendarIntegrations, setCalendarIntegrations] = useState<Integration[]>([])
  const [emailIntegrations, setEmailIntegrations] = useState<Integration[]>([])
  const [mcpIntegrations, setMcpIntegrations] = useState<MCPIntegration[]>([])
  const [loading, setLoading] = useState(true)
  const [connectingCalendar, setConnectingCalendar] = useState(false)
  const [connectingEmail, setConnectingEmail] = useState(false)
  const [connectingMCP, setConnectingMCP] = useState(false)
  const [mcpServerUrl, setMcpServerUrl] = useState('http://localhost:8003')
  const [mcpServerName, setMcpServerName] = useState('MCP Server')
  const [gmailNeedsReconnect, setGmailNeedsReconnect] = useState(false)
  const [gmailStatusMessage, setGmailStatusMessage] = useState<string | null>(null)
  const [calendarNeedsReconnect, setCalendarNeedsReconnect] = useState(false)
  const [calendarStatusMessage, setCalendarStatusMessage] = useState<string | null>(null)
  const [isRefreshingIntegrations, setIsRefreshingIntegrations] = useState(false)
  const [editingIntegrationId, setEditingIntegrationId] = useState<string | null>(null)
  const [editingIntegrationName, setEditingIntegrationName] = useState<string>('')
  
  // Use global status panel
  const { addStatusMessage } = useStatus()
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'

  useEffect(() => {
    loadIntegrations()
    // Check if we're returning from OAuth callback
    const urlParams = new URLSearchParams(window.location.search)
    if (urlParams.get('success') === 'true') {
      // Integration connected successfully - UI will update automatically
      // Clean URL
      window.history.replaceState({}, document.title, '/integrations')
      // Reload integrations to show the new connection
      loadIntegrations()
    }
    
    return () => {}
  }, [])

  const handleSaveIntegrationName = async (integrationId: string) => {
    if (!editingIntegrationName.trim()) {
      addStatusMessage('error', 'Server name cannot be empty')
      return
    }

    try {
      await integrationsApi.mcp.updateIntegration(integrationId, editingIntegrationName.trim())
      setEditingIntegrationId(null)
      setEditingIntegrationName('')
      await loadIntegrations()
      addStatusMessage('success', 'Server name updated successfully')
    } catch (error: any) {
      console.error('Error updating integration name:', error)
      addStatusMessage('error', `Error updating name: ${error.response?.data?.detail || error.message}`)
    }
  }


  const loadIntegrations = async (options: { promptCleanup?: boolean } = {}) => {
    const { promptCleanup = false } = options
    if (promptCleanup) {
      setIsRefreshingIntegrations(true)
    } else {
      setLoading(true)
    }

    const maybeCleanupDuplicates = async (
      calendarList: Integration[],
      emailList: Integration[]
    ): Promise<{ calendarIds: string[]; emailIds: string[] } | null> => {
      type DuplicateGroup = {
        type: 'calendar' | 'email'
        provider: string
        toDelete: Integration[]
        total: number
      }

      const duplicateGroups: DuplicateGroup[] = []

      const collectDuplicates = (list: Integration[], type: 'calendar' | 'email') => {
        const byProvider = new Map<string, Integration[]>()
        list.forEach((integration) => {
          const key = integration.provider || 'unknown'
          const current = byProvider.get(key) || []
          current.push(integration)
          byProvider.set(key, current)
        })
        byProvider.forEach((items, provider) => {
          if (items.length > 1) {
            const toDelete = items.slice(0, -1) // keep the last one (assumed latest)
            duplicateGroups.push({
              type,
              provider,
              toDelete,
              total: items.length,
            })
          }
        })
      }

      collectDuplicates(calendarList, 'calendar')
      collectDuplicates(emailList, 'email')

      if (duplicateGroups.length === 0) {
        return null
      }

      const summaryLines = duplicateGroups.map((group) => {
        const providerLabel =
          group.type === 'calendar'
            ? `${group.provider.charAt(0).toUpperCase()}${group.provider.slice(1)} Calendar`
            : `${group.provider.charAt(0).toUpperCase()}${group.provider.slice(1)} Email`
        return `${providerLabel}: trovate ${group.total} integrazioni (verranno rimosse ${group.toDelete.length})`
      })

      const confirmed = window.confirm(
        `Sono state trovate integrazioni duplicate:\n\n${summaryLines.join(
          '\n'
        )}\n\nVuoi rimuovere automaticamente quelle meno recenti?`
      )

      if (!confirmed) {
        return null
      }

      const deletedCalendarIds: string[] = []
      const deletedEmailIds: string[] = []

      for (const group of duplicateGroups) {
        for (const integration of group.toDelete) {
          try {
            if (group.type === 'calendar') {
              await integrationsApi.calendar.deleteIntegration(integration.id)
              deletedCalendarIds.push(integration.id)
            } else {
              await integrationsApi.email.deleteIntegration(integration.id)
              deletedEmailIds.push(integration.id)
            }
          } catch (error: any) {
            const detail = error.response?.data?.detail || error.message
            addStatusMessage(
              'error',
              `Errore rimozione integrazione ${integration.provider}: ${detail}`
            )
          }
        }
      }

      const totalDeleted = deletedCalendarIds.length + deletedEmailIds.length
      if (totalDeleted > 0) {
        addStatusMessage(
          'success',
          `Rimosse automaticamente ${totalDeleted} integrazioni duplicate`
        )
      } else {
        addStatusMessage('info', 'Nessuna integrazione duplicata è stata rimossa')
      }

      return {
        calendarIds: deletedCalendarIds,
        emailIds: deletedEmailIds,
      }
    }

    try {
      const [calendarResponse, emailResponse, mcpResponse] = await Promise.all([
        integrationsApi.calendar.listIntegrations(),
        integrationsApi.email.listIntegrations(),
        integrationsApi.mcp.listIntegrations().catch(() => ({ data: { integrations: [] } })),
      ])
      let calendarList: Integration[] = calendarResponse.data.integrations || []
      let emailList: Integration[] = emailResponse.data.integrations || []

      if (promptCleanup) {
        const cleanupResult = await maybeCleanupDuplicates(calendarList, emailList)
        if (cleanupResult) {
          if (cleanupResult.calendarIds.length > 0) {
            calendarList = calendarList.filter(
              (integration) => !cleanupResult.calendarIds.includes(integration.id)
            )
          }
          if (cleanupResult.emailIds.length > 0) {
            emailList = emailList.filter(
              (integration) => !cleanupResult.emailIds.includes(integration.id)
            )
          }
        }
      }

      setCalendarIntegrations(calendarList)
      setEmailIntegrations(emailList)
      setMcpIntegrations(mcpResponse.data.integrations || [])
    } catch (error) {
      console.error('Error loading integrations:', error)
    } finally {
      if (promptCleanup) {
        setIsRefreshingIntegrations(false)
      } else {
        setLoading(false)
      }
    }
  }

  const connectGoogleCalendar = async (integrationId?: string) => {
    setConnectingCalendar(true)
    try {
      const response = await integrationsApi.calendar.authorize(integrationId)
      if (response.data?.authorization_url) {
        window.location.href = response.data.authorization_url
      } else {
        throw new Error('No authorization URL received')
      }
    } catch (error: any) {
      console.error('Error connecting Google Calendar:', error)
      const errorMsg = error.response?.data?.detail || error.message
      console.error('Error connecting calendar:', errorMsg)
      addStatusMessage('error', `Errore connessione Calendario: ${errorMsg}`)
      setConnectingCalendar(false)
    }
  }

  const connectGmail = async (integrationId?: string) => {
    setConnectingEmail(true)
    try {
      const response = await integrationsApi.email.authorize(integrationId)
      if (response.data?.authorization_url) {
        window.location.href = response.data.authorization_url
      } else {
        throw new Error('No authorization URL received')
      }
    } catch (error: any) {
      console.error('Error connecting Gmail:', error)
      const errorMsg = error.response?.data?.detail || error.message
      console.error('Error connecting email:', errorMsg)
      addStatusMessage('error', `Errore connessione Email: ${errorMsg}`)
      setConnectingEmail(false)
    }
  }

  const testGmailConnection = async () => {
    try {
      if (!gmailIntegration) {
        console.warn('Nessuna integrazione Gmail trovata')
        return
      }

      const response = await integrationsApi.email.summarize(gmailIntegration.id, 3)
      
      // Test successful - show in status panel
      if (response.data?.summary) {
        addStatusMessage('success', `Gmail: Trovate email non lette`)
      } else {
        addStatusMessage('success', 'Gmail: Connessione funzionante')
      }
      setGmailNeedsReconnect(false)
      setGmailStatusMessage(null)
    } catch (error: any) {
      const detail = error.response?.data?.detail
      const reason = detail?.reason || detail?.message || error.message
      console.error('Error testing Gmail:', reason)
      if (error.response?.status === 401) {
        setGmailNeedsReconnect(true)
        const message =
          typeof detail === 'object' && detail?.message
            ? detail.message
            : 'Autorizzazione Gmail scaduta o revocata. Ricollega l’account.'
        setGmailStatusMessage(message)
        addStatusMessage('warning', message)
      } else {
        addStatusMessage('error', `Gmail: errore nel test - ${reason}`)
      }
    }
  }

  const disconnectCalendar = async (integrationId: string) => {
    if (!integrationId) {
      return
    }
    
    if (!confirm('Sei sicuro di voler rimuovere questa integrazione del calendario?')) {
      return
    }
    
    try {
      await integrationsApi.calendar.deleteIntegration(integrationId)
      loadIntegrations()
      // UI updates automatically, no alert needed
    } catch (error: any) {
      console.error('Error disconnecting calendar:', error)
      console.error('Errore nella rimozione:', error.response?.data?.detail || error.message)
    }
  }

  const disconnectEmail = async (integrationId: string) => {
    if (!integrationId) {
      return
    }
    
    if (!confirm('Sei sicuro di voler rimuovere questa integrazione email?')) {
      return
    }
    
    try {
      await integrationsApi.email.deleteIntegration(integrationId)
      loadIntegrations()
      // UI updates automatically, no alert needed
    } catch (error: any) {
      console.error('Error disconnecting email:', error)
      console.error('Errore nella rimozione:', error.response?.data?.detail || error.message)
    }
  }

  const testCalendarConnection = async () => {
    try {
      // Get first enabled Google Calendar integration
      const googleIntegration = calendarIntegrations.find(
        (i) => i.provider === 'google' && i.enabled
      )
      
      if (!googleIntegration) {
        console.warn('Nessuna integrazione Google Calendar trovata')
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
        addStatusMessage('success', `Calendario: Connessione funzionante! Trovati ${count} eventi oggi`)
      } else {
        addStatusMessage('info', 'Calendario: Connessione funzionante, nessun evento trovato')
      }
      setCalendarNeedsReconnect(false)
      setCalendarStatusMessage(null)
    } catch (error: any) {
      const detail = error.response?.data?.detail
      const message =
        typeof detail === 'object' && detail?.message
          ? detail.message
          : detail || error.message
      console.error('Error testing calendar:', message)
      if (error.response?.status === 401) {
        setCalendarNeedsReconnect(true)
        setCalendarStatusMessage(
          message || 'Autorizzazione Google Calendar scaduta o revocata. Ricollega l’account.'
        )
        addStatusMessage(
          'warning',
          message || 'Autorizzazione Google Calendar scaduta o revocata. Ricollega l’account.'
        )
      } else {
        addStatusMessage('error', `Calendario: errore nel test - ${message}`)
      }
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">Caricamento...</div>
      </div>
    )
  }

  const googleCalendarIntegrations = calendarIntegrations.filter(
    (i) => i.provider === 'google' && i.enabled
  )
  const primaryCalendarIntegration =
    googleCalendarIntegrations.length > 0
      ? googleCalendarIntegrations[googleCalendarIntegrations.length - 1]
      : undefined
  const hasGoogleCalendar = googleCalendarIntegrations.length > 0
  const gmailIntegrations = emailIntegrations.filter((i) => i.provider === 'google' && i.enabled)
  const gmailIntegration = gmailIntegrations.length > 0 ? gmailIntegrations[gmailIntegrations.length - 1] : undefined
  const hasGmailIntegration = gmailIntegrations.length > 0

  return (
    <div className="min-h-screen p-8 bg-gray-50 dark:bg-gray-900">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <Link
              href="/"
              className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 transition-colors"
            >
              <ArrowLeft size={20} />
              <span>Torna alla Home</span>
            </Link>
            <button
              onClick={() => loadIntegrations({ promptCleanup: true })}
              disabled={isRefreshingIntegrations}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-200 hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
              title="Ricarica le integrazioni e rimuovi eventuali duplicati"
            >
              {isRefreshingIntegrations ? (
                <RefreshCw size={18} className="animate-spin" />
              ) : (
                <RotateCcw size={18} />
              )}
              <span className="hidden sm:inline text-sm font-medium">Ricarica</span>
            </button>
          </div>
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
              {calendarNeedsReconnect && (
                <div className="p-4 bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-300 dark:border-yellow-700 rounded-lg">
                  <p className="text-sm text-yellow-900 dark:text-yellow-200 font-medium">
                    {calendarStatusMessage ||
                      'Il token di autorizzazione Google Calendar è scaduto. Ricollega l’account per continuare a leggere gli eventi.'}
                  </p>
                </div>
              )}
              {googleCalendarIntegrations.length > 1 && (
                <div className="p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg text-sm text-amber-900 dark:text-amber-100">
                  Sono presenti {googleCalendarIntegrations.length} integrazioni Google Calendar abilitate. Mantieni solo quella più recente e rimuovi le altre per evitare token scaduti.
                </div>
              )}
              <div className="flex gap-3">
                <button
                  onClick={testCalendarConnection}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"
                >
                  <RefreshCw size={18} />
                  Test Connessione
                </button>
                {primaryCalendarIntegration && (
                  <button
                    onClick={() => {
                      if (primaryCalendarIntegration?.id) {
                        disconnectCalendar(primaryCalendarIntegration.id)
                      } else {
                        console.warn('Nessuna integrazione trovata')
                      }
                    }}
                    className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 flex items-center gap-2"
                  >
                    <Trash2 size={18} />
                    Rimuovi
                  </button>
                )}
                <button
                  onClick={() => connectGoogleCalendar(primaryCalendarIntegration?.id)}
                  disabled={connectingCalendar}
                  className="px-4 py-2 bg-amber-500 text-white rounded-lg hover:bg-amber-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {connectingCalendar ? (
                    <>
                      <RefreshCw size={18} className="animate-spin" />
                      Richiesta in corso...
                    </>
                  ) : (
                    <>
                      <RefreshCw size={18} />
                      Ricollega Calendar
                    </>
                  )}
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
              onClick={() => connectGoogleCalendar()}
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
            {hasGmailIntegration ? (
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

          {hasGmailIntegration ? (
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
              {gmailNeedsReconnect && (
                <div className="p-4 bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-300 dark:border-yellow-700 rounded-lg">
                  <p className="text-sm text-yellow-900 dark:text-yellow-200 font-medium">
                    {gmailStatusMessage ||
                      'Il token di autorizzazione Gmail è scaduto. Ricollega l’account per continuare a leggere le email.'}
                  </p>
                </div>
              )}
              {gmailIntegrations.length > 1 && (
                <div className="p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg text-sm text-amber-900 dark:text-amber-100">
                  Sono presenti {gmailIntegrations.length} integrazioni Gmail abilitate. Mantieni solo quella più recente e rimuovi le altre per evitare token scaduti.
                </div>
              )}
              <div className="flex gap-3">
                <button
                  onClick={testGmailConnection}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"
                >
                  <RefreshCw size={18} />
                  Test Connessione
                </button>
                {gmailIntegration && (
                  <button
                    onClick={() => {
                      if (gmailIntegration?.id) {
                        disconnectEmail(gmailIntegration.id)
                      } else {
                        console.warn('Nessuna integrazione trovata')
                      }
                    }}
                    className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 flex items-center gap-2"
                  >
                    <Trash2 size={18} />
                    Rimuovi
                  </button>
                )}
                <button
                  onClick={() => connectGmail(gmailIntegration?.id)}
                  disabled={connectingEmail}
                  className="px-4 py-2 bg-amber-500 text-white rounded-lg hover:bg-amber-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {connectingEmail ? (
                    <>
                      <RefreshCw size={18} className="animate-spin" />
                      Richiesta in corso...
                    </>
                  ) : (
                    <>
                      <RefreshCw size={18} />
                      Ricollega Gmail
                    </>
                  )}
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
                onClick={() => connectGmail()}
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

        {/* WhatsApp Section */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 mb-6">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <MessageSquare size={32} className="text-green-600" />
              <div>
                <h2 className="text-2xl font-semibold">WhatsApp</h2>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Leggi e invia messaggi WhatsApp
                </p>
              </div>
            </div>
            {/* Removed WhatsApp-specific state */}
            <div className="flex items-center gap-2 text-gray-400">
              <XCircle size={24} />
              <span>Non collegato</span>
            </div>
          </div>

          {/* Removed WhatsApp-specific logic */}
          <div className="space-y-4">
            <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg">
              <p className="text-sm text-yellow-800 dark:text-yellow-200">
                WhatsApp è stata rimossa dalle integrazioni.
              </p>
            </div>
          </div>
        </div>

        {/* MCP Integration Section - Only for Admin */}
        {isAdmin && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 mb-6">
            <div className="flex items-center gap-3 mb-4">
              <Server size={24} className="text-blue-600" />
              <h2 className="text-2xl font-bold">MCP Server</h2>
            </div>

            <div className="space-y-4">
              {mcpIntegrations.length > 0 ? (
                mcpIntegrations.map((integration) => {
                  const isEditing = editingIntegrationId === integration.id
                  
                  return (
                    <div key={integration.id} className="border rounded-lg p-4">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex-1">
                          {isEditing ? (
                            <div className="flex items-center gap-2">
                              <input
                                type="text"
                                value={editingIntegrationName}
                                onChange={(e) => setEditingIntegrationName(e.target.value)}
                                className="flex-1 px-2 py-1 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                                placeholder="Server name"
                                autoFocus
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') {
                                    handleSaveIntegrationName(integration.id)
                                  } else if (e.key === 'Escape') {
                                    setEditingIntegrationId(null)
                                    setEditingIntegrationName('')
                                  }
                                }}
                              />
                              <button
                                onClick={() => handleSaveIntegrationName(integration.id)}
                                className="p-1 text-green-600 hover:bg-green-50 dark:hover:bg-green-900/20 rounded"
                                title="Save"
                              >
                                <Save size={16} />
                              </button>
                              <button
                                onClick={() => {
                                  setEditingIntegrationId(null)
                                  setEditingIntegrationName('')
                                }}
                                className="p-1 text-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 rounded"
                                title="Cancel"
                              >
                                <X size={16} />
                              </button>
                            </div>
                          ) : (
                            <>
                              <div className="flex items-center gap-2">
                                <h3 className="font-semibold">{integration.name}</h3>
                                <button
                                  onClick={() => {
                                    setEditingIntegrationId(integration.id)
                                    setEditingIntegrationName(integration.name)
                                  }}
                                  className="p-1 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                                  title="Edit name"
                                >
                                  <Edit2 size={14} />
                                </button>
                              </div>
                              <p className="text-sm text-gray-600 dark:text-gray-400">{integration.server_url}</p>
                            </>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          {integration.enabled ? (
                            <CheckCircle size={20} className="text-green-500" />
                          ) : (
                            <XCircle size={20} className="text-gray-400" />
                          )}
                        </div>
                      </div>

                      <div className="flex gap-2">
                      {integration.oauth_required && (
                        <div className="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded-lg flex items-center gap-2 text-sm">
                          <span>OAuth required - authorize in</span>
                          <Link href="/settings/profile" className="text-blue-600 dark:text-blue-400 hover:underline">
                            Profile Settings
                          </Link>
                        </div>
                      )}
                      <button
                        onClick={async () => {
                          try {
                            const response = await integrationsApi.mcp.test(integration.id)
                            addStatusMessage('success', `MCP test: Found ${response.data.tools_count || 0} tools`)
                            console.log(`MCP test: Found ${response.data.tools_count || 0} tools`)
                          } catch (error: any) {
                            console.error('MCP test failed:', error.response?.data?.detail || error.message)
                            addStatusMessage('error', `MCP test failed: ${error.response?.data?.detail || error.message}`)
                          }
                        }}
                        className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
                      >
                        Test
                      </button>
                      <button
                        onClick={async () => {
                          try {
                            const debug = await integrationsApi.mcp.debug(integration.id)
                            console.log('MCP Debug Info:', debug.data)
                            addStatusMessage('info', 'MCP Debug info logged to console')
                          } catch (error: any) {
                            console.error('MCP Debug failed:', error.response?.data?.detail || error.message)
                            addStatusMessage('error', `MCP Debug failed: ${error.response?.data?.detail || error.message}`)
                          }
                        }}
                        className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-xs"
                        title="Show raw MCP responses and connection status"
                      >
                        Debug
                      </button>
                      <button
                        onClick={async () => {
                          if (!confirm('Are you sure you want to remove this MCP integration?')) {
                            return
                          }

                          try {
                            await integrationsApi.mcp.deleteIntegration(integration.id)
                            await loadIntegrations()
                            addStatusMessage('success', 'MCP integration removed successfully')
                          } catch (error: any) {
                            console.error('Error:', error.response?.data?.detail || error.message)
                            addStatusMessage('error', `Error removing MCP: ${error.response?.data?.detail || error.message}`)
                          }
                        }}
                        className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 flex items-center gap-2"
                      >
                        <Trash2 size={16} />
                        Remove
                      </button>
                    </div>
                  </div>
                  )
                })
              ) : (
                <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
                  <p className="text-sm text-gray-700 dark:text-gray-200">
                    Nessun server MCP connesso. Aggiungine uno utilizzando il form sottostante.
                  </p>
                </div>
              )}

              <div className="p-4 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
                <h3 className="font-semibold mb-3">Connect New MCP Server</h3>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium mb-1">Server URL</label>
                    <input
                      type="text"
                      value={mcpServerUrl}
                      onChange={(e) => setMcpServerUrl(e.target.value)}
                      placeholder="http://localhost:8003 (Google Workspace MCP) or http://localhost:8080 (MCP Gateway)"
                      className="w-full p-2 border rounded-md bg-gray-50 dark:bg-gray-700"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Name (optional)</label>
                    <input
                      type="text"
                      value={mcpServerName}
                      onChange={(e) => setMcpServerName(e.target.value)}
                      placeholder="MCP Server"
                      className="w-full p-2 border rounded-md bg-gray-50 dark:bg-gray-700"
                    />
                  </div>
                  <button
                    onClick={async () => {
                      setConnectingMCP(true)
                      try {
                        const response = await integrationsApi.mcp.connect(mcpServerUrl, mcpServerName)
                        await loadIntegrations()

                        const toolCount = response.data.count || 0
                        addStatusMessage('success', `MCP collegato (${toolCount} tool${toolCount === 1 ? '' : 's'})`)

                        if (toolCount === 0) {
                          console.warn('Il server MCP collegato non ha tool disponibili.')
                        }
                      } catch (error: any) {
                        console.error('Error connecting MCP:', error.response?.data?.detail || error.message)
                        addStatusMessage('error', `Errore connessione MCP: ${error.response?.data?.detail || error.message}`)
                      } finally {
                        setConnectingMCP(false)
                      }
                    }}
                    disabled={connectingMCP}
                    className="px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                  >
                    {connectingMCP ? (
                      <>
                        <RefreshCw size={18} className="animate-spin" />
                        Connessione in corso...
                      </>
                    ) : (
                      <>
                        <ExternalLink size={18} />
                        Connetti nuovo MCP
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
 