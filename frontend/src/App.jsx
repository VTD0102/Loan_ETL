import { Routes, Route, Navigate } from 'react-router-dom'
import Navbar          from './components/common/Navbar'
import ProtectedRoute  from './components/ProtectedRoute'
import { isMock }      from './services/api'

// Pages
import LandingPage           from './pages/customer/Landing'
import RegisterPage          from './pages/customer/Register'
import LoginPage             from './pages/customer/Login'
import DashboardPage         from './pages/customer/Dashboard'
import ApplyPage             from './pages/customer/Apply'
import ApplicationDetailPage from './pages/customer/ApplicationDetail'
import SubmitPersonalInfoPage from './pages/customer/SubmitInfo'
import ChatbotPage           from './pages/customer/Chat'

const NotFound = () => (
  <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 text-center px-4">
    <p className="text-6xl font-extrabold text-primary-200 mb-4">404</p>
    <h1 className="text-xl font-bold text-gray-800 mb-2">Trang không tồn tại</h1>
    <p className="text-gray-500 mb-6">Đường dẫn bạn truy cập không đúng hoặc đã bị xoá.</p>
    <a href="/" className="btn-primary">Về trang chủ</a>
  </div>
)

// Mock mode banner
const MockBanner = () => (
  <div className="fixed bottom-3 right-3 z-50 flex items-center gap-2 bg-amber-500 text-white text-xs font-semibold px-3 py-1.5 rounded-full shadow-lg select-none">
    <span className="w-2 h-2 bg-white rounded-full animate-pulse" />
    MOCK MODE — không kết nối backend
  </div>
)

// Layout that includes Navbar (used for most pages)
const WithNav = ({ children }) => (
  <>
    <Navbar />
    {children}
  </>
)

// Chat & Apply use full-screen layouts without the top nav clutter on the chat UI
// so we still include nav but page manages its own header on mobile

const App = () => (
  <>
  <Routes>
    {/* Public */}
    <Route path="/"          element={<WithNav><LandingPage /></WithNav>} />
    <Route path="/register"  element={<WithNav><RegisterPage /></WithNav>} />
    <Route path="/login"     element={<WithNav><LoginPage /></WithNav>} />

    {/* Protected — customer */}
    <Route path="/dashboard" element={
      <ProtectedRoute>
        <WithNav><DashboardPage /></WithNav>
      </ProtectedRoute>
    } />
    <Route path="/apply" element={
      <ProtectedRoute>
        <WithNav><ApplyPage /></WithNav>
      </ProtectedRoute>
    } />
    <Route path="/application/:id" element={
      <ProtectedRoute>
        <WithNav><ApplicationDetailPage /></WithNav>
      </ProtectedRoute>
    } />
    <Route path="/submit-info/:id" element={
      <ProtectedRoute>
        <WithNav><SubmitPersonalInfoPage /></WithNav>
      </ProtectedRoute>
    } />
    <Route path="/chat" element={
      <ProtectedRoute>
        <div className="flex flex-col h-screen overflow-hidden">
          <Navbar />
          <div className="flex-1 overflow-hidden">
            <ChatbotPage />
          </div>
        </div>
      </ProtectedRoute>
    } />

    {/* Fallback */}
    <Route path="*" element={<NotFound />} />
  </Routes>

  {isMock && <MockBanner />}
</>
)

export default App
