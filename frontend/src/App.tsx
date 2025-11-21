import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'sonner'
import { DashboardPage } from './pages/DashboardPage'
import { ProfessionnelsPage } from './pages/ProfessionnelsPage'
import { CopropriétésPage } from './pages/CopriprietesPage'
import { CopropriétairesPage } from './pages/CoproprietairesPage'
import { ImportPage } from './pages/ImportPage'
import { DocumentsPage } from './pages/DocumentsPage'
import { SettingsPage } from './pages/SettingsPage'
import { DigestPage } from './pages/DigestPage'
import { MainChatPageV2 } from './pages/MainChatPageV2'
import { AppLayout } from './components/layout/AppLayout'
import { useEffect } from 'react'
import { adminApi } from './lib/api'
import { ActiveDocumentsProvider } from './contexts/ActiveDocumentsContext'

const queryClient = new QueryClient()

function App() {
  // Fetch notifications
  const fetchNotifications = async () => {
    try {
      await adminApi.getNotifications()
    } catch (error) {
      console.error('Failed to fetch notifications:', error)
    }
  }

  // Initial fetch and polling every 30 seconds
  useEffect(() => {
    fetchNotifications()
    const interval = setInterval(fetchNotifications, 30000) // 30 seconds
    return () => clearInterval(interval)
  }, [])
  return (
    <QueryClientProvider client={queryClient}>
      <ActiveDocumentsProvider>
        <BrowserRouter>
        <div className="min-h-screen bg-background">
          {/* Toast Notifications - Style subtil comme ChatGPT */}
          <Toaster
            position="bottom-right"
            expand={false}
            richColors
            closeButton
            duration={3000}
            toastOptions={{
              style: {
                background: 'hsl(var(--background))',
                color: 'hsl(var(--foreground))',
                border: '1px solid hsl(var(--border))',
                fontSize: '14px',
                padding: '12px 16px',
                borderRadius: '12px',
                boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)',
              },
              className: 'backdrop-blur-sm',
            }}
          />

          {/* Routes */}
          <Routes>
            {/* Main Chat Page - V2 UI Redesign avec couleurs pastel */}
            <Route path="/" element={<MainChatPageV2 />} />

            {/* Admin routes with AppLayout (sidebar navigation) */}
            <Route path="/admin" element={<AppLayout />}>
              <Route index element={<DashboardPage />} />
              <Route path="professionnels" element={<ProfessionnelsPage />} />
              <Route path="coproprietes" element={<CopropriétésPage />} />
              <Route path="coproprietaires" element={<CopropriétairesPage />} />
              <Route path="import" element={<ImportPage />} />
              <Route path="documents" element={<DocumentsPage />} />
              <Route path="digest" element={<DigestPage />} />
              <Route path="settings" element={<SettingsPage />} />
            </Route>
          </Routes>
        </div>
      </BrowserRouter>
      </ActiveDocumentsProvider>
    </QueryClientProvider>
  )
}

export default App
