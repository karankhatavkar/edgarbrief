import { Routes, Route, Navigate } from 'react-router-dom'
import AuthPage from '@/pages/AuthPage'
import ChatHome from '@/pages/ChatHome'
import ChatThread from '@/pages/ChatThread'
import LandingPage from '@/pages/LandingPage'
import { ChatLayout } from '@/components/chat/ChatLayout'
import { ProtectedRoute } from '@/components/ProtectedRoute'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/auth" element={<AuthPage />} />

      <Route
        element={
          <ProtectedRoute>
            <ChatLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/app" element={<ChatHome />} />
        <Route path="/c/:threadId" element={<ChatThread />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
