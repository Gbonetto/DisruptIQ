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
import { ChatPage } from './pages/ChatPage'
import { DigestPage } from './pages/DigestPage'
import { ChatPageV2 } from './pages/ChatPageV2'
import { MainChatPage } from './pages/MainChatPage'
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
            {/* Main Chat Page - Interface principale simplifiée */}
            <Route path="/" element={<MainChatPage />} />

            {/* V2 UI Redesign - Pastel Colors */}
            <Route path="/v2" element={<MainChatPageV2 />} />

            {/* Legacy chat pages */}
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/chat-v2" element={<ChatPageV2 />} />

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
