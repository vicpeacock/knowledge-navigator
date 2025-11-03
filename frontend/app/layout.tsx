import './globals.css'

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
      <body>{children}</body>
    </html>
  )
}

