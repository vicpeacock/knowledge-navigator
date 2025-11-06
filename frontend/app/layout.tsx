import './globals.css'
import { StatusProvider } from '@/components/StatusPanel'
import { BackendStatus } from '@/components/BackendStatus'

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
        <BackendStatus>
          <StatusProvider>
            {children}
          </StatusProvider>
        </BackendStatus>
      </body>
    </html>
  )
}

