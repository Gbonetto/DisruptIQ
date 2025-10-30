import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'sonner'
import { DashboardPage } from './pages/DashboardPage'
import { ChatPage } from './pages/ChatPage'
import { AdminPage } from './pages/AdminPage'
import { Home, MessageSquare, Settings } from 'lucide-react'

const queryClient = new QueryClient()

function App() {
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

          {/* Navigation */}
          <nav className="border-b">
            <div className="container mx-auto px-4 py-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center text-primary-foreground font-bold">
                    D
                  </div>
                  <span className="text-xl font-bold">DisruptIQ</span>
                </div>

                <div className="flex gap-4">
                  <Link
                    to="/"
                    className="flex items-center gap-2 px-4 py-2 rounded-md hover:bg-accent transition-colors"
                  >
                    <Home className="w-4 h-4" />
                    Dashboard
                  </Link>
                  <Link
                    to="/chat"
                    className="flex items-center gap-2 px-4 py-2 rounded-md hover:bg-accent transition-colors"
                  >
                    <MessageSquare className="w-4 h-4" />
                    Assistant
                  </Link>
                  <Link
                    to="/admin"
                    className="flex items-center gap-2 px-4 py-2 rounded-md hover:bg-accent transition-colors"
                  >
                    <Settings className="w-4 h-4" />
                    Admin
                  </Link>
                </div>
              </div>
            </div>
          </nav>

          {/* Routes */}
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/admin" element={<AdminPage />} />
          </Routes>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
