import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'sonner'
import { DashboardPage } from './pages/DashboardPage'
import { ProfessionnelsPage } from './pages/ProfessionnelsPage'
import { CopropriétésPage } from './pages/CopriprietesPage'
import { CopropriétairesPage } from './pages/CoproprietairesPage'
import { ImportPage } from './pages/ImportPage'
import { DocumentsPage } from './pages/DocumentsPage'
import { SettingsPage } from './pages/SettingsPage'
import { ChatPage } from './pages/ChatPage'
import { DigestPage } from './pages/DigestPage'
import { AssistantPage } from './pages/AssistantPage'
import { AppLayout } from './components/layout/AppLayout'
import { useEffect } from 'react'
import { adminApi } from './lib/api'

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
      <BrowserRouter>
        <div className="min-h-screen bg-background">
          {/* Toast Notifications */}
          <Toaster
            position="top-right"
            expand={true}
            richColors
            closeButton
            duration={4000}
          />

          {/* Routes */}
          <Routes>
            {/* Redirect root to admin dashboard */}
            <Route path="/" element={<Navigate to="/admin" replace />} />

            {/* Chat page (standalone, not in admin layout) */}
            <Route path="/chat" element={<ChatPage />} />

            {/* Admin routes with AppLayout (sidebar navigation) */}
            <Route path="/admin" element={<AppLayout />}>
              <Route index element={<DashboardPage />} />
              <Route path="professionnels" element={<ProfessionnelsPage />} />
              <Route path="coproprietes" element={<CopropriétésPage />} />
              <Route path="coproprietaires" element={<CopropriétairesPage />} />
              <Route path="import" element={<ImportPage />} />
              <Route path="documents" element={<DocumentsPage />} />
              <Route path="digest" element={<DigestPage />} />
              <Route path="assistant" element={<AssistantPage />} />
              <Route path="settings" element={<SettingsPage />} />
            </Route>
          </Routes>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
