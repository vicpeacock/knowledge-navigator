'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { integrationsApi } from '@/lib/api'
import { Calendar, CheckCircle, XCircle, RefreshCw, ExternalLink, Mail, ArrowLeft, Trash2, Server, Settings, MessageSquare } from 'lucide-react'

interface Integration {
  id: string
  provider: string
  enabled: boolean
}

interface MCPIntegration extends Integration {
  name: string
  server_url: string
  selected_tools: string[]
}

export default function IntegrationsPage() {
  const [calendarIntegrations, setCalendarIntegrations] = useState<Integration[]>([])
  const [emailIntegrations, setEmailIntegrations] = useState<Integration[]>([])
  const [mcpIntegrations, setMcpIntegrations] = useState<MCPIntegration[]>([])
  const [loading, setLoading] = useState(true)
  const [connectingCalendar, setConnectingCalendar] = useState(false)
  const [connectingEmail, setConnectingEmail] = useState(false)
  const [connectingWhatsApp, setConnectingWhatsApp] = useState(false)
  const [whatsappConnected, setWhatsappConnected] = useState(false)
  const [whatsappCheckInterval, setWhatsappCheckInterval] = useState<NodeJS.Timeout | null>(null)
  const [connectingMCP, setConnectingMCP] = useState(false)
  const [mcpServerUrl, setMcpServerUrl] = useState('http://host.docker.internal:8080')
  const [mcpServerName, setMcpServerName] = useState('MCP Server')
  const [selectedMcpIntegration, setSelectedMcpIntegration] = useState<string | null>(null)
  const [mcpTools, setMcpTools] = useState<any[]>([])
  const [selectedTools, setSelectedTools] = useState<string[]>([])
  const [loadingTools, setLoadingTools] = useState(false)
  const [isSaving, setIsSaving] = useState(false) // Flag to prevent useEffect from interfering during save

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
    
    // Cleanup WhatsApp check interval on unmount
    return () => {
      if (whatsappCheckInterval) {
        clearInterval(whatsappCheckInterval)
      }
    }
  }, [])

  // Helper function to load tools for an integration
  const loadToolsForIntegration = async (integrationId: string, skipLoadingState = false) => {
    if (!skipLoadingState) {
      setLoadingTools(true)
    }
    try {
      const toolsResponse = await integrationsApi.mcp.getTools(integrationId)
      console.log('loadToolsForIntegration - Full tools response:', JSON.stringify(toolsResponse.data, null, 2))
      
      const availableTools = toolsResponse.data.available_tools || []
      const selectedToolsFromServer = toolsResponse.data.selected_tools || []
      
      console.log('loadToolsForIntegration - Loaded tools:', {
        integrationId: integrationId,
        available: availableTools.length,
        selected: selectedToolsFromServer.length,
        selectedNames: selectedToolsFromServer,
        availableNames: availableTools.map((t: any) => t.name)
      })
      
      // Ensure selected tools match available tool names (case-sensitive)
      const availableToolNames = availableTools.map((t: any) => t.name)
      const validSelectedTools = selectedToolsFromServer.filter((toolName: string) => 
        availableToolNames.includes(toolName)
      )
      
      if (validSelectedTools.length !== selectedToolsFromServer.length) {
        console.warn('loadToolsForIntegration - Some selected tools not found in available tools:', {
          selected: selectedToolsFromServer,
          valid: validSelectedTools,
          available: availableToolNames
        })
      }
      
      // Use functional state update to ensure we're setting the correct state
      setMcpTools(availableTools)
      setSelectedTools(() => {
        console.log('Setting selectedTools to:', validSelectedTools)
        return validSelectedTools
      })
      
      console.log('loadToolsForIntegration - After setting state - selectedTools:', validSelectedTools)
      
      // Return the loaded tools for verification
      return { availableTools, selectedTools: validSelectedTools }
    } catch (error: any) {
      console.error('loadToolsForIntegration - Error loading tools:', error)
      alert(`Error loading tools: ${error.response?.data?.detail || error.message}`)
      setSelectedMcpIntegration(null)
      setMcpTools([])
      setSelectedTools([])
      throw error
    } finally {
      if (!skipLoadingState) {
        setLoadingTools(false)
      }
    }
  }

  // Reload tools when an integration is selected
  useEffect(() => {
    // Don't reload if we're in the middle of saving
    if (isSaving) {
      console.log('Skipping useEffect reload - save in progress')
      return
    }
    
    if (selectedMcpIntegration) {
      console.log('Loading tools for integration:', selectedMcpIntegration)
      loadToolsForIntegration(selectedMcpIntegration).catch((error) => {
        console.error('Error in useEffect loadToolsForIntegration:', error)
        // Don't show alert here - loadToolsForIntegration already handles it
      })
    } else {
      // Clear tools when no integration is selected
      setMcpTools([])
      setSelectedTools([])
    }
  }, [selectedMcpIntegration, isSaving])

  const loadIntegrations = async () => {
    try {
      const [calendarResponse, emailResponse, mcpResponse] = await Promise.all([
        integrationsApi.calendar.listIntegrations(),
        integrationsApi.email.listIntegrations(),
        integrationsApi.mcp.listIntegrations().catch(() => ({ data: { integrations: [] } })),
      ])
      setCalendarIntegrations(calendarResponse.data.integrations || [])
      setEmailIntegrations(emailResponse.data.integrations || [])
      setMcpIntegrations(mcpResponse.data.integrations || [])
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

  const connectWhatsApp = async () => {
    setConnectingWhatsApp(true)
    try {
      // Start setup in background - don't wait for it
      const setupPromise = integrationsApi.whatsapp.setup(false, undefined, false).catch((error) => {
        console.error('WhatsApp setup error:', error)
        // Show error but don't block
        if (error.response?.data?.detail) {
          alert(`Errore durante il setup: ${error.response.data.detail}`)
        } else if (error.message && !error.message.includes('timeout')) {
          alert(`Errore: ${error.message}`)
        }
        return { data: { success: false } }
      })
      
      // Show immediate feedback
      alert('WhatsApp Web si sta aprendo in una finestra Chrome separata. Il controllo dello stato avverrà automaticamente.')
      
      // Wait for setup with timeout (but don't block UI)
      const response = await Promise.race([
        setupPromise,
        new Promise((resolve) => setTimeout(() => resolve({ data: { success: true, message: 'Setup in corso...' } }), 8000))
      ])
      
      // Start auto-check immediately (even if setup is still running)
      let checkCount = 0
      const maxChecks = 30 // Check for 90 seconds (30 * 3 seconds)
      
      const checkInterval = setInterval(async () => {
        checkCount++
        try {
          const statusResponse = await integrationsApi.whatsapp.getStatus()
          if (statusResponse.data?.authenticated) {
            setWhatsappConnected(true)
            clearInterval(checkInterval)
            setWhatsappCheckInterval(null)
            alert('✅ WhatsApp è connesso!')
          } else if (checkCount >= maxChecks) {
            clearInterval(checkInterval)
            setWhatsappCheckInterval(null)
            // Don't show alert, just stop checking silently
          }
        } catch (error) {
          console.error('Error checking status:', error)
          if (checkCount >= maxChecks) {
            clearInterval(checkInterval)
            setWhatsappCheckInterval(null)
          }
        }
      }, 3000) // Check every 3 seconds
      
      setWhatsappCheckInterval(checkInterval)
      
      // Check response if available
      if (response?.data?.success && response.data.message) {
        console.log('Setup response:', response.data.message)
      }
    } catch (error: any) {
      console.error('Error:', error)
      // Don't show alert here - already handled above
    } finally {
      setConnectingWhatsApp(false)
    }
  }

  const checkWhatsAppStatus = async () => {
    try {
      const statusResponse = await integrationsApi.whatsapp.getStatus()
      if (statusResponse.data?.authenticated) {
        setWhatsappConnected(true)
        alert('WhatsApp è connesso!')
      } else {
        setWhatsappConnected(false)
        alert(`WhatsApp non ancora autenticato. Stato: ${statusResponse.data?.status || 'unknown'}. ${statusResponse.data?.message || ''}`)
      }
    } catch (error: any) {
      console.error('Error checking WhatsApp status:', error)
      alert(`Errore nel controllo: ${error.response?.data?.detail || error.message}`)
    }
  }

  const testWhatsAppConnection = async () => {
    try {
      // First check status
      await checkWhatsAppStatus()
      
      // If authenticated, try to get messages
      if (whatsappConnected) {
        const response = await integrationsApi.whatsapp.getMessages(undefined, 3)
        if (response.data?.success && response.data?.messages) {
          const count = response.data.count || 0
          alert(`Connessione funzionante! Trovati ${count} messaggi recenti.`)
        } else {
          alert('Connessione funzionante, ma nessun messaggio trovato.')
        }
      }
    } catch (error: any) {
      console.error('Error testing WhatsApp:', error)
      alert(`Errore nel test: ${error.response?.data?.detail || error.message}`)
    }
  }

  const disconnectWhatsApp = async () => {
    if (!confirm('Sei sicuro di voler chiudere la sessione WhatsApp?')) {
      return
    }
    
    try {
      await integrationsApi.whatsapp.close()
      setWhatsappConnected(false)
      alert('Sessione WhatsApp chiusa con successo')
    } catch (error: any) {
      console.error('Error disconnecting WhatsApp:', error)
      alert(`Errore nella disconnessione: ${error.response?.data?.detail || error.message}`)
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
            {whatsappConnected ? (
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

          {whatsappConnected ? (
            <div className="space-y-4">
              <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
                <p className="text-sm text-green-800 dark:text-green-200">
                  ✓ WhatsApp è collegato e funzionante. Puoi chiedere al chatbot di:
                </p>
                <ul className="mt-2 ml-4 list-disc text-sm text-green-700 dark:text-green-300">
                  <li>Leggere i messaggi recenti</li>
                  <li>Inviare messaggi a contatti</li>
                  <li>Cercare messaggi per contatto</li>
                </ul>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={checkWhatsAppStatus}
                  className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center gap-2"
                >
                  <RefreshCw size={18} />
                  Verifica Stato
                </button>
                <button
                  onClick={testWhatsAppConnection}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"
                >
                  <RefreshCw size={18} />
                  Test Connessione
                </button>
                <button
                  onClick={disconnectWhatsApp}
                  className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 flex items-center gap-2"
                >
                  <Trash2 size={18} />
                  Disconnetti
                </button>
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
                  Verrà aperta una finestra Chrome separata e isolata per WhatsApp. 
                  Non interferirà con il tuo Chrome personale. 
                  Potresti dover autenticare scansionando il QR code la prima volta.
                </p>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={checkWhatsAppStatus}
                  className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 flex items-center gap-2"
                >
                  <RefreshCw size={18} />
                  Verifica Stato
                </button>
                <button
                  onClick={connectWhatsApp}
                  disabled={connectingWhatsApp}
                  className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {connectingWhatsApp ? (
                    <>
                      <RefreshCw size={18} className="animate-spin" />
                      Connessione in corso...
                    </>
                  ) : (
                    <>
                      <ExternalLink size={18} />
                      Connetti WhatsApp
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* MCP Integration Section */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <Server size={24} className="text-blue-600" />
            <h2 className="text-2xl font-bold">MCP Server</h2>
          </div>

          {mcpIntegrations.length > 0 ? (
            <div className="space-y-4">
              {mcpIntegrations.map((integration) => (
                <div key={integration.id} className="border rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <h3 className="font-semibold">{integration.name}</h3>
                      <p className="text-sm text-gray-600 dark:text-gray-400">{integration.server_url}</p>
                      <p className="text-xs text-gray-500 mt-1">
                        {integration.selected_tools?.length || 0} tools selected
                      </p>
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
                    <button
                      onClick={async () => {
                        // Toggle: if already open, close it; otherwise open it
                        const isCurrentlyOpen = selectedMcpIntegration === integration.id
                        
                        if (isCurrentlyOpen) {
                          // Close the panel
                          setSelectedMcpIntegration(null)
                          setMcpTools([])
                          setSelectedTools([])
                          return
                        }
                        
                        // Close other integrations first (if any) - but don't clear selectedTools yet
                        if (selectedMcpIntegration && selectedMcpIntegration !== integration.id) {
                          setSelectedMcpIntegration(null)
                          setMcpTools([])
                          // Don't clear selectedTools here - it will be loaded from server
                          // Small delay to allow state update
                          await new Promise(resolve => setTimeout(resolve, 100))
                        }
                        
                        // Open this integration's tools panel
                        // The useEffect will handle loading the tools automatically
                        setSelectedMcpIntegration(integration.id)
                      }}
                      className={`px-4 py-2 rounded-lg flex items-center gap-2 ${
                        selectedMcpIntegration === integration.id
                          ? 'bg-blue-700 text-white'
                          : 'bg-blue-600 text-white hover:bg-blue-700'
                      }`}
                    >
                      <Settings size={16} />
                      {selectedMcpIntegration === integration.id ? 'Close' : 'Manage Tools'}
                    </button>
                    <button
                      onClick={async () => {
                        try {
                          const response = await integrationsApi.mcp.test(integration.id)
                          alert(`Connection successful! Found ${response.data.tools_count || 0} tools.`)
                        } catch (error: any) {
                          alert(`Test failed: ${error.response?.data?.detail || error.message}`)
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
                          
                          // Show user-friendly message
                          if (debug.data.connection_test?.reachable === false) {
                            const suggestion = debug.data.connection_test.suggestion || ''
                            alert(`❌ MCP Server not reachable!\n\n${debug.data.connection_test.error || 'Connection failed'}\n\n${suggestion}\n\nFull details in browser console (F12).`)
                          } else if (debug.data.tools_list?.response) {
                            const toolsResp = debug.data.tools_list.response
                            const toolsCount = toolsResp?.result?.tools?.length || 0
                            alert(`✅ Connection successful!\n\nTools/list response received.\n\nFull response in browser console (F12).\n\nParsed tools count: ${toolsCount}`)
                          } else {
                            alert(`Debug info logged to console. Check browser DevTools (F12) > Console tab.\n\nConnection test: ${debug.data.connection_test?.reachable ? '✅ Reachable' : '❌ Not reachable'}`)
                          }
                        } catch (error: any) {
                          alert(`Debug failed: ${error.response?.data?.detail || error.message}`)
                        }
                      }}
                      className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-xs"
                      title="Show raw MCP responses and connection status"
                    >
                      Debug
                    </button>
                    <button
                      onClick={async () => {
                        if (confirm('Are you sure you want to remove this MCP integration?')) {
                          try {
                            await integrationsApi.mcp.deleteIntegration(integration.id)
                            // Reset state if removing the currently selected integration
                            if (selectedMcpIntegration === integration.id) {
                              setSelectedMcpIntegration(null)
                              setMcpTools([])
                              setSelectedTools([])
                            }
                            await loadIntegrations()
                          } catch (error: any) {
                            alert(`Error: ${error.response?.data?.detail || error.message}`)
                          }
                        }
                      }}
                      className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 flex items-center gap-2"
                    >
                      <Trash2 size={16} />
                      Remove
                    </button>
                  </div>

                  {selectedMcpIntegration === integration.id && (
                    <div className="mt-4 p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
                      <h4 className="font-semibold mb-3">Select Tools to Enable</h4>
                      {loadingTools ? (
                        <div>Loading tools...</div>
                      ) : (
                        <>
                          <div className="max-h-64 overflow-y-auto space-y-2 mb-4">
                            {mcpTools.length === 0 ? (
                              <p className="text-sm text-gray-500">No tools available</p>
                            ) : (
                              mcpTools.map((tool: any) => (
                                <label key={tool.name} className="flex items-center gap-2 cursor-pointer">
                                  <input
                                    type="checkbox"
                                    checked={selectedTools.includes(tool.name)}
                                    onChange={(e) => {
                                      if (e.target.checked) {
                                        setSelectedTools([...selectedTools, tool.name])
                                      } else {
                                        setSelectedTools(selectedTools.filter((t) => t !== tool.name))
                                      }
                                    }}
                                    className="rounded"
                                  />
                                  <span className="text-sm">
                                    <strong>{tool.name}</strong>
                                    {tool.description && (
                                      <span className="text-gray-600 dark:text-gray-400 ml-2">
                                        - {tool.description.substring(0, 100)}
                                        {tool.description.length > 100 ? '...' : ''}
                                      </span>
                                    )}
                                  </span>
                                </label>
                              ))
                            )}
                          </div>
                          <div className="flex gap-2">
                            <button
                              onClick={async () => {
                                try {
                                  setIsSaving(true) // Prevent useEffect from interfering
                                  
                                  // Save the tools - keep a copy of what we're saving
                                  const toolsToSave = [...selectedTools] // Make a copy to avoid state issues
                                  console.log('Saving tools:', toolsToSave, 'count:', toolsToSave.length)
                                  
                                  if (toolsToSave.length === 0) {
                                    alert('No tools selected!')
                                    setIsSaving(false)
                                    return
                                  }
                                  
                                  await integrationsApi.mcp.selectTools(integration.id, toolsToSave)
                                  console.log('Tools saved to server successfully')
                                  
                                  // DON'T reload from server - just keep the current state
                                  // The tools are already selected in the UI, and we just saved them
                                  // Reloading would cause a race condition or timing issue
                                  
                                  // Update the integration count in the list without full reload
                                  setMcpIntegrations(prev => prev.map(i => 
                                    i.id === integration.id 
                                      ? { ...i, selected_tools: toolsToSave }
                                      : i
                                  ))
                                  
                                  // Re-enable useEffect after state is updated
                                  setIsSaving(false)
                                  
                                  // Show success message
                                  alert(`Selected ${toolsToSave.length} tools successfully!`)
                                } catch (error: any) {
                                  console.error('Error saving tools:', error)
                                  setIsSaving(false) // Re-enable useEffect even on error
                                  alert(`Error: ${error.response?.data?.detail || error.message}`)
                                }
                              }}
                              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                            >
                              Save Selection
                            </button>
                            <button
                              onClick={async () => {
                                // Cancel: reload tools to restore selected state from server
                                try {
                                  const toolsResponse = await integrationsApi.mcp.getTools(integration.id)
                                  setSelectedTools(toolsResponse.data.selected_tools || [])
                                } catch (error) {
                                  console.error('Error reloading tools:', error)
                                }
                                setSelectedMcpIntegration(null)
                                setMcpTools([])
                                setSelectedTools([])
                              }}
                              className="px-4 py-2 bg-gray-300 dark:bg-gray-600 text-gray-800 dark:text-white rounded-lg hover:bg-gray-400 dark:hover:bg-gray-500"
                            >
                              Cancel
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  )}
                </div>
              ))}
              
              <div className="mt-4 p-4 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
                <h3 className="font-semibold mb-3">Connect New MCP Server</h3>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium mb-1">Server URL</label>
                    <input
                      type="text"
                      value={mcpServerUrl}
                      onChange={(e) => setMcpServerUrl(e.target.value)}
                      placeholder="http://host.docker.internal:8080 or http://localhost:8080"
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
                        
                        // Auto-open tool selection for the new integration after state updates
                        const toolCount = response.data.count || 0
                        if (response.data.integration_id && response.data.available_tools && toolCount > 0) {
                          setTimeout(() => {
                            setSelectedMcpIntegration(response.data.integration_id)
                            setMcpTools(response.data.available_tools || [])
                            setSelectedTools([])
                            alert(`Connected successfully! Found ${toolCount} tools. Please select which tools to enable.`)
                          }, 200)
                        } else if (toolCount === 0) {
                          alert(`Connected successfully to ${mcpServerUrl}, but no tools were found. Please check the server configuration and backend logs for details.`)
                        } else {
                          alert(`Connected! Found ${toolCount} tools.`)
                        }
                      } catch (error: any) {
                        alert(`Error: ${error.response?.data?.detail || error.message}`)
                      } finally {
                        setConnectingMCP(false)
                      }
                    }}
                    disabled={connectingMCP || !mcpServerUrl}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {connectingMCP ? 'Connecting...' : 'Connect'}
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                <p className="text-sm text-blue-800 dark:text-blue-200">
                  Connect to a Docker MCP Gateway server to access external tools like browser, maps, and academic papers.
                </p>
              </div>
              <div className="space-y-3">
                <div>
                  <label className="block text-sm font-medium mb-1">Server URL</label>
                  <input
                    type="text"
                    value={mcpServerUrl}
                    onChange={(e) => setMcpServerUrl(e.target.value)}
                    placeholder="http://host.docker.internal:8080 or http://localhost:8080"
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
                      if (toolCount > 0) {
                        alert(`Connected successfully! Found ${toolCount} tools. Click "Manage Tools" to select which tools to enable.`)
                      } else {
                        alert(`Connected successfully to ${mcpServerUrl}, but no tools were found. Please check the server configuration and logs.`)
                      }
                    } catch (error: any) {
                      alert(`Error: ${error.response?.data?.detail || error.message}`)
                    } finally {
                      setConnectingMCP(false)
                    }
                  }}
                  disabled={connectingMCP || !mcpServerUrl}
                  className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {connectingMCP ? (
                    <>
                      <RefreshCw size={18} className="animate-spin" />
                      Connecting...
                    </>
                  ) : (
                    <>
                      <Server size={18} />
                      Connect MCP Server
                    </>
                  )}
                </button>
              </div>
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

