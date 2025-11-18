'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

interface DayTransitionDialogProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
  newSessionId: string
}

export default function DayTransitionDialog({
  isOpen,
  onClose,
  onConfirm,
  newSessionId,
}: DayTransitionDialogProps) {
  const router = useRouter()
  const [isProcessing, setIsProcessing] = useState(false)

  if (!isOpen) return null

  const handleProceed = async () => {
    setIsProcessing(true)
    try {
      // Call onConfirm which will handle resending the message with proceed_with_new_day flag
      // The parent component will handle navigation after the message is sent
      onConfirm()
      // Small delay to allow message to be sent, then navigate
      setTimeout(() => {
        router.push(`/sessions/${newSessionId}`)
      }, 500)
    } catch (error) {
      console.error('Error transitioning to new session:', error)
      setIsProcessing(false)
    }
  }

  const handleStay = () => {
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-md w-full mx-4 shadow-xl">
        <h2 className="text-xl font-bold mb-4 text-gray-900 dark:text-white">
          Nuovo Giorno Iniziato
        </h2>
        <p className="text-gray-700 dark:text-gray-300 mb-6">
          È iniziato un nuovo giorno! Vuoi continuare con la sessione di oggi o rimanere su quella di ieri?
        </p>
        <div className="flex gap-3 justify-end">
          <button
            onClick={handleStay}
            disabled={isProcessing}
            className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Rimani su Ieri
          </button>
          <button
            onClick={handleProceed}
            disabled={isProcessing}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isProcessing ? 'Caricamento...' : 'Continua con Oggi'}
          </button>
        </div>
      </div>
    </div>
  )
}

