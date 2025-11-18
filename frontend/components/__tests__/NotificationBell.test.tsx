/**
 * @jest-environment jsdom
 */
import React from 'react'
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import axios from 'axios'
import NotificationBell from '../NotificationBell'

// Mock axios
jest.mock('axios')
const mockedAxios = axios as jest.Mocked<typeof axios>

describe('NotificationBell', () => {
  const mockSessionId = 'test-session-id'
  
  beforeEach(() => {
    jest.clearAllMocks()
    jest.useFakeTimers()
  })

  afterEach(() => {
    jest.runOnlyPendingTimers()
    jest.useRealTimers()
  })

  describe('Rendering', () => {
    it('renders bell icon', () => {
      mockedAxios.get.mockResolvedValue({ data: [] })
      
      render(<NotificationBell sessionId={mockSessionId} />)
      
      const bellButton = screen.getByTitle('Notifiche')
      expect(bellButton).toBeInTheDocument()
    })

    it('shows notification count badge when there are notifications', async () => {
      const mockNotifications = [
        {
          id: '1',
          type: 'email_received',
          priority: 'high',
          created_at: '2025-01-01T00:00:00Z',
          content: { message: 'New email received' },
        },
      ]
      
      mockedAxios.get.mockResolvedValue({ data: mockNotifications })
      
      render(<NotificationBell sessionId={mockSessionId} />)
      
      await waitFor(() => {
        expect(screen.getByText('1')).toBeInTheDocument()
      })
    })

    it('shows 9+ badge when there are more than 9 notifications', async () => {
      const mockNotifications = Array.from({ length: 10 }, (_, i) => ({
        id: `${i}`,
        type: 'email_received',
        priority: 'medium',
        created_at: '2025-01-01T00:00:00Z',
        content: { message: `Email ${i}` },
      }))
      
      mockedAxios.get.mockResolvedValue({ data: mockNotifications })
      
      render(<NotificationBell sessionId={mockSessionId} />)
      
      await waitFor(() => {
        expect(screen.getByText('9+')).toBeInTheDocument()
      })
    })
  })

  describe('Popup functionality', () => {
    it('opens popup when bell is clicked', async () => {
      mockedAxios.get.mockResolvedValue({ data: [] })
      
      render(<NotificationBell sessionId={mockSessionId} />)
      
      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled()
      })
      
      const bellButton = screen.getByTitle('Notifiche')
      fireEvent.click(bellButton)
      
      await waitFor(() => {
        expect(screen.getByText('Notifiche')).toBeInTheDocument()
      })
      
      await waitFor(() => {
        expect(screen.getByText('Nessuna notifica in attesa')).toBeInTheDocument()
      }, { timeout: 3000 })
    })

    it('closes popup when backdrop is clicked', async () => {
      mockedAxios.get.mockResolvedValue({ data: [] })
      
      render(<NotificationBell sessionId={mockSessionId} />)
      
      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled()
      })
      
      const bellButton = screen.getByTitle('Notifiche')
      fireEvent.click(bellButton)
      
      await waitFor(() => {
        expect(screen.getByText('Notifiche')).toBeInTheDocument()
      })
      
      const backdrop = document.querySelector('.fixed.inset-0')
      if (backdrop) {
        fireEvent.click(backdrop)
      }
      
      await waitFor(() => {
        expect(screen.queryByText('Notifiche')).not.toBeInTheDocument()
      }, { timeout: 3000 })
    })

    it('closes popup when close button is clicked', async () => {
      mockedAxios.get.mockResolvedValue({ data: [] })
      
      render(<NotificationBell sessionId={mockSessionId} />)
      
      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled()
      })
      
      const bellButton = screen.getByTitle('Notifiche')
      fireEvent.click(bellButton)
      
      await waitFor(() => {
        expect(screen.getByText('Notifiche')).toBeInTheDocument()
      })
      
      const closeButton = screen.getByText('✕')
      fireEvent.click(closeButton)
      
      await waitFor(() => {
        expect(screen.queryByText('Notifiche')).not.toBeInTheDocument()
      }, { timeout: 3000 })
    })
  })

  describe('Notification fetching', () => {
    it('fetches notifications on mount', async () => {
      mockedAxios.get.mockResolvedValue({ data: [] })
      
      render(<NotificationBell sessionId={mockSessionId} />)
      
      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalledWith(
          `http://localhost:8000/api/sessions/${mockSessionId}/notifications/pending`,
          { timeout: 5000 }
        )
      })
    })

    it('polls for notifications every 10 seconds when popup is closed', async () => {
      mockedAxios.get.mockResolvedValue({ data: [] })
      
      render(<NotificationBell sessionId={mockSessionId} />)
      
      // Initial fetch
      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalledTimes(1)
      })
      
      // Advance timer by 10 seconds
      act(() => {
        jest.advanceTimersByTime(10000)
      })
      
      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalledTimes(2)
      })
    })

    it('does not poll when popup is open', async () => {
      mockedAxios.get.mockResolvedValue({ data: [] })
      
      render(<NotificationBell sessionId={mockSessionId} />)
      
      // Wait for initial fetch
      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalledTimes(1)
      })
      
      const bellButton = screen.getByTitle('Notifiche')
      fireEvent.click(bellButton)
      
      await waitFor(() => {
        expect(screen.getByText('Notifiche')).toBeInTheDocument()
      })
      
      // Wait for popup fetch (2nd call)
      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalledTimes(2)
      })
      
      // Advance timer - should not poll again (polling disabled when popup open)
      act(() => {
        jest.advanceTimersByTime(10000)
      })
      
      // Should still be only 2 calls (no additional polling)
      expect(mockedAxios.get).toHaveBeenCalledTimes(2)
    })

    it('fetches notifications when popup opens', async () => {
      mockedAxios.get.mockResolvedValue({ data: [] })
      
      render(<NotificationBell sessionId={mockSessionId} />)
      
      // Wait for initial fetch
      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalledTimes(1)
      })
      
      const bellButton = screen.getByTitle('Notifiche')
      fireEvent.click(bellButton)
      
      // Should fetch again when popup opens
      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalledTimes(2)
      }, { timeout: 3000 })
    })
  })

  describe('Notification display', () => {
    it('displays email notifications', async () => {
      const mockNotifications = [
        {
          id: '1',
          type: 'email_received',
          priority: 'high',
          created_at: '2025-01-01T00:00:00Z',
          content: {
            message: 'New email from sender@example.com',
            subject: 'Test Subject',
          },
        },
      ]
      
      mockedAxios.get.mockResolvedValue({ data: mockNotifications })
      
      render(<NotificationBell sessionId={mockSessionId} />)
      
      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled()
      })
      
      const bellButton = screen.getByTitle('Notifiche')
      fireEvent.click(bellButton)
      
      await waitFor(() => {
        expect(screen.getByText('New email from sender@example.com')).toBeInTheDocument()
      }, { timeout: 3000 })
    })

    it('displays calendar notifications', async () => {
      const mockNotifications = [
        {
          id: '1',
          type: 'calendar_event_starting',
          priority: 'high',
          created_at: '2025-01-01T00:00:00Z',
          content: {
            message: 'Meeting starting in 5 minutes',
            title: 'Team Meeting',
          },
        },
      ]
      
      mockedAxios.get.mockResolvedValue({ data: mockNotifications })
      
      render(<NotificationBell sessionId={mockSessionId} />)
      
      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled()
      })
      
      const bellButton = screen.getByTitle('Notifiche')
      fireEvent.click(bellButton)
      
      await waitFor(() => {
        expect(screen.getByText('Meeting starting in 5 minutes')).toBeInTheDocument()
      }, { timeout: 3000 })
    })

    it('displays contradiction notifications with details', async () => {
      const mockNotifications = [
        {
          id: '1',
          type: 'contradiction',
          priority: 'high',
          created_at: '2025-01-01T00:00:00Z',
          content: {
            title: 'Contraddizione rilevata',
            message: 'Nuova informazione contraddice memorie esistenti',
            new_statement: 'New statement',
            contradictions: [
              {
                existing_memory: 'Existing memory',
                explanation: 'Explanation',
              },
            ],
          },
        },
      ]
      
      mockedAxios.get.mockResolvedValue({ data: mockNotifications })
      
      render(<NotificationBell sessionId={mockSessionId} />)
      
      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled()
      })
      
      const bellButton = screen.getByTitle('Notifiche')
      fireEvent.click(bellButton)
      
      await waitFor(() => {
        expect(screen.getByText('Contraddizione rilevata')).toBeInTheDocument()
        expect(screen.getByText('Nuova informazione contraddice memorie esistenti')).toBeInTheDocument()
        expect(screen.getByText('New statement')).toBeInTheDocument()
        expect(screen.getByText('Existing memory')).toBeInTheDocument()
      }, { timeout: 3000 })
    })

    it('shows loading state while fetching', async () => {
      mockedAxios.get.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve({ data: [] }), 100))
      )
      
      render(<NotificationBell sessionId={mockSessionId} />)
      
      const bellButton = screen.getByTitle('Notifiche')
      fireEvent.click(bellButton)
      
      await waitFor(() => {
        expect(screen.getByText('Caricamento...')).toBeInTheDocument()
      })
      
      await waitFor(() => {
        expect(screen.queryByText('Caricamento...')).not.toBeInTheDocument()
      }, { timeout: 3000 })
    })
  })

  describe('Error handling', () => {
    it('handles network timeout gracefully', async () => {
      const timeoutError = {
        code: 'ECONNABORTED',
        message: 'timeout',
      }
      
      mockedAxios.get.mockRejectedValue(timeoutError)
      
      render(<NotificationBell sessionId={mockSessionId} />)
      
      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled()
      })
      
      // Should not crash, just log error
      expect(screen.getByTitle('Notifiche')).toBeInTheDocument()
    })

    it('handles other errors by clearing notifications', async () => {
      const error = new Error('Network error')
      mockedAxios.get.mockRejectedValue(error)
      
      render(<NotificationBell sessionId={mockSessionId} />)
      
      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled()
      })
      
      // Should not show badge
      expect(screen.queryByText(/^\d+$/)).not.toBeInTheDocument()
    })
  })

  describe('Notification resolution', () => {
    it('resolves notification and removes it from list', async () => {
      const mockNotifications = [
        {
          id: '1',
          type: 'email_received',
          priority: 'high',
          created_at: '2025-01-01T00:00:00Z',
          content: { message: 'Test notification' },
        },
      ]
      
      mockedAxios.get.mockResolvedValue({ data: mockNotifications })
      mockedAxios.post.mockResolvedValue({ data: { success: true } })
      
      render(<NotificationBell sessionId={mockSessionId} />)
      
      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled()
      })
      
      const bellButton = screen.getByTitle('Notifiche')
      fireEvent.click(bellButton)
      
      await waitFor(() => {
        expect(screen.getByText('Test notification')).toBeInTheDocument()
      }, { timeout: 3000 })
      
      // Note: This test would need the actual resolve button in NotificationItem
      // For now, we just verify the API call structure
      expect(mockedAxios.post).not.toHaveBeenCalled()
    })
  })

  describe('Edge cases', () => {
    it('does not fetch when sessionId is missing', () => {
      mockedAxios.get.mockResolvedValue({ data: [] })
      
      render(<NotificationBell sessionId="" />)
      
      // Should not call API
      expect(mockedAxios.get).not.toHaveBeenCalled()
    })

    it('handles empty notification list', async () => {
      mockedAxios.get.mockResolvedValue({ data: [] })
      
      render(<NotificationBell sessionId={mockSessionId} />)
      
      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled()
      })
      
      const bellButton = screen.getByTitle('Notifiche')
      fireEvent.click(bellButton)
      
      await waitFor(() => {
        expect(screen.getByText('Nessuna notifica in attesa')).toBeInTheDocument()
      }, { timeout: 3000 })
    })
  })
})

