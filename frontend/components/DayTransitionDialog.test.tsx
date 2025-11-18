/**
 * @jest-environment jsdom
 */
import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { useRouter } from 'next/navigation'
import DayTransitionDialog from './DayTransitionDialog'

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
}))

describe('DayTransitionDialog', () => {
  const mockPush = jest.fn()
  const mockOnClose = jest.fn()
  const mockOnConfirm = jest.fn()

  beforeEach(() => {
    jest.clearAllMocks()
    ;(useRouter as jest.Mock).mockReturnValue({
      push: mockPush,
    })
  })

  it('renders nothing when isOpen is false', () => {
    const { container } = render(
      <DayTransitionDialog
        isOpen={false}
        onClose={mockOnClose}
        onConfirm={mockOnConfirm}
        newSessionId="test-session-id"
      />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders dialog when isOpen is true', () => {
    render(
      <DayTransitionDialog
        isOpen={true}
        onClose={mockOnClose}
        onConfirm={mockOnConfirm}
        newSessionId="test-session-id"
      />
    )

    expect(screen.getByText('Nuovo Giorno Iniziato')).toBeInTheDocument()
    expect(
      screen.getByText(
        /È iniziato un nuovo giorno! Vuoi continuare con la sessione di oggi o rimanere su quella di ieri?/
      )
    ).toBeInTheDocument()
    expect(screen.getByText('Rimani su Ieri')).toBeInTheDocument()
    expect(screen.getByText('Continua con Oggi')).toBeInTheDocument()
  })

  it('calls onClose when "Rimani su Ieri" is clicked', () => {
    render(
      <DayTransitionDialog
        isOpen={true}
        onClose={mockOnClose}
        onConfirm={mockOnConfirm}
        newSessionId="test-session-id"
      />
    )

    const stayButton = screen.getByText('Rimani su Ieri')
    fireEvent.click(stayButton)

    expect(mockOnClose).toHaveBeenCalledTimes(1)
    expect(mockOnConfirm).not.toHaveBeenCalled()
    expect(mockPush).not.toHaveBeenCalled()
  })

  it('calls onConfirm and navigates when "Continua con Oggi" is clicked', async () => {
    jest.useFakeTimers()

    render(
      <DayTransitionDialog
        isOpen={true}
        onClose={mockOnClose}
        onConfirm={mockOnConfirm}
        newSessionId="test-session-id"
      />
    )

    const proceedButton = screen.getByText('Continua con Oggi')
    fireEvent.click(proceedButton)

    // onConfirm should be called immediately
    expect(mockOnConfirm).toHaveBeenCalledTimes(1)

    // Fast-forward time to trigger navigation
    jest.advanceTimersByTime(500)

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/sessions/test-session-id')
    })

    jest.useRealTimers()
  })

  it('disables buttons when processing', () => {
    render(
      <DayTransitionDialog
        isOpen={true}
        onClose={mockOnClose}
        onConfirm={mockOnConfirm}
        newSessionId="test-session-id"
      />
    )

    const proceedButton = screen.getByText('Continua con Oggi')
    fireEvent.click(proceedButton)

    // After clicking, button should show loading state
    expect(screen.getByText('Caricamento...')).toBeInTheDocument()
  })

  it('handles errors gracefully', async () => {
    const consoleError = jest.spyOn(console, 'error').mockImplementation(() => {})
    mockOnConfirm.mockImplementation(() => {
      throw new Error('Test error')
    })

    render(
      <DayTransitionDialog
        isOpen={true}
        onClose={mockOnClose}
        onConfirm={mockOnConfirm}
        newSessionId="test-session-id"
      />
    )

    const proceedButton = screen.getByText('Continua con Oggi')
    fireEvent.click(proceedButton)

    await waitFor(() => {
      expect(consoleError).toHaveBeenCalledWith(
        'Error transitioning to new session:',
        expect.any(Error)
      )
    })

    consoleError.mockRestore()
  })
})

