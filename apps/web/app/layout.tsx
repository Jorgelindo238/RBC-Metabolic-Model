import { GeistSans } from 'geist/font/sans'
import './globals.css'
import { PlatformShell } from '../components/platform/PlatformShell.tsx'
import { getServerProductContext } from '../lib/server-product-context.mjs'

export const metadata = {
  title: 'RoBoCop Scientific Platform',
  description: 'Supabase-backed researcher platform for calibration evidence and future scientific workspaces.',
  icons: { icon: '/favicon.svg' },
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const productContext = await getServerProductContext()

  return (
    <html lang="en" className={`${GeistSans.variable} antialiased`}>
      <body className="app-body font-sans" suppressHydrationWarning>
        <div className="app-frame">
          <PlatformShell productContext={productContext}>
            {children}
          </PlatformShell>
        </div>
      </body>
    </html>
  )
}
