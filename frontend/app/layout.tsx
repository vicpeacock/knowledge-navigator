import './globals.css'
import { StatusProvider } from '@/components/StatusPanel'
import { BackendStatus } from '@/components/BackendStatus'
import { AuthProviderWrapper } from '@/components/AuthProviderWrapper'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { PerformanceMonitor } from '@/components/PerformanceMonitor'

export const metadata = {
  title: 'Knowledge Navigator',
  description: 'AI Assistant with multi-level memory',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        <ErrorBoundary>
          <PerformanceMonitor />
          <BackendStatus>
            <AuthProviderWrapper>
              <StatusProvider>
                {children}
              </StatusProvider>
            </AuthProviderWrapper>
          </BackendStatus>
        </ErrorBoundary>
      </body>
    </html>
  )
}

