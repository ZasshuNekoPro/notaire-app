/**
 * Layout racine Next.js avec providers React
 */
import './globals.css'

// Force dynamic rendering for all pages
export const dynamic = 'force-dynamic'
export const revalidate = 0
import { AuthProvider } from '@/lib/auth-context'
import { ToastProvider } from '@/components/ui/Toast'

export const metadata = {
  title: 'Notaire App',
  description: 'Application notariale IA - Estimation, Succession, RAG Juridique',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="fr">
      <body>
        <ToastProvider>
          <AuthProvider>
            {children}
          </AuthProvider>
        </ToastProvider>
      </body>
    </html>
  )
}