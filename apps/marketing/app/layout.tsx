import { GeistSans } from 'geist/font/sans'
import './globals.css'

export const metadata = {
  title: 'airbc - AI-Powered Blood Bag Conservation Platform',
  description:
    'airbc is an AI-powered red blood cell storage research and blood bag conservation monitoring platform. Simulate, monitor, and interpret metabolic changes during storage.',
  icons: { icon: '/favicon.svg' },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${GeistSans.variable} antialiased`}>
      <body suppressHydrationWarning>{children}</body>
    </html>
  )
}
