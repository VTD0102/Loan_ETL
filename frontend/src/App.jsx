import { Routes, Route, Navigate } from 'react-router-dom'
import Navbar          from './components/common/Navbar'
import ProtectedRoute  from './components/ProtectedRoute'
import { isMock }      from './services/api'
import useAuthStore    from './store/authStore'

// ── Customer Pages ────────────────────────────────
import LandingPage            from './pages/customer/Landing'
import RegisterPage           from './pages/customer/Register'
import LoginPage              from './pages/customer/Login'
import DashboardPage          from './pages/customer/Dashboard'
import ApplyPage              from './pages/customer/Apply'
import ApplicationDetailPage  from './pages/customer/ApplicationDetail'
import SubmitPersonalInfoPage from './pages/customer/SubmitInfo'
import ChatbotPage            from './pages/customer/Chat'
import HistoryPage            from './pages/customer/History'

// ── Admin Pages ───────────────────────────────────
import AdminDashboardPage          from './pages/admin/Dashboard'
import PendingApplicationsPage     from './pages/admin/PendingList'
import AllApplicationsPage         from './pages/admin/ApplicationList'
import AdminApplicationDetailPage  from './pages/admin/ApplicationDetail'
import PersonalInfoViewPage        from './pages/admin/PersonalInfoView'
import AdminProfilePage             from './pages/admin/Profile'

// ── Admin Components ──────────────────────────────
import AdminLayout from './components/admin/AdminLayout'
import CustomerLayout from './components/customer/CustomerLayout'

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

/**
 * AdminProtectedRoute — kiểm tra token + role === 'admin'
 */
const AdminProtectedRoute = ({ children }) => {
  const token = useAuthStore((s) => s.token)
  const user  = useAuthStore((s) => s.user)

  if (!token) {
    return <Navigate to="/login" replace />
  }
  if (user?.role !== 'admin') {
    return <Navigate to="/login" replace />
  }
  return children
}

const App = () => (
  <>
  <Routes>
    {/* ── Public ───────────────────────────────── */}
    <Route path="/"          element={<WithNav><LandingPage /></WithNav>} />
    <Route path="/register"  element={<WithNav><RegisterPage /></WithNav>} />
    <Route path="/login"     element={<WithNav><LoginPage /></WithNav>} />

    {/* ── Protected — customer (CustomerLayout wraps all) */}
    <Route path="/" element={
      <ProtectedRoute>
        <CustomerLayout />
      </ProtectedRoute>
    }>
      <Route path="dashboard"        element={<DashboardPage />} />
      <Route path="apply"            element={<ApplyPage />} />
      <Route path="application/:id"  element={<ApplicationDetailPage />} />
      <Route path="submit-info/:id"  element={<SubmitPersonalInfoPage />} />
      <Route path="chat"             element={<ChatbotPage />} />
      <Route path="history"          element={<HistoryPage />} />
      <Route path="profile"          element={<AdminProfilePage />} />
    </Route>

    {/* ── Admin — public ───────────────────────── */}
    <Route path="/admin/login" element={<Navigate to="/login" replace />} />

    {/* ── Admin — protected (AdminLayout wraps all) */}
    <Route path="/admin" element={
      <AdminProtectedRoute>
        <AdminLayout />
      </AdminProtectedRoute>
    }>
      {/* Index: redirect to dashboard */}
      <Route index element={<Navigate to="/admin/dashboard" replace />} />
      <Route path="dashboard"           element={<AdminDashboardPage />} />
      <Route path="pending"             element={<PendingApplicationsPage />} />
      <Route path="applications"        element={<AllApplicationsPage />} />
      <Route path="application/:id"     element={<AdminApplicationDetailPage />} />
      <Route path="personal-info/:id"   element={<PersonalInfoViewPage />} />
      <Route path="profile"             element={<AdminProfilePage />} />
    </Route>

    {/* Fallback */}
    <Route path="*" element={<NotFound />} />
    {/* History is now nested under CustomerLayout */}
  </Routes>

  {isMock && <MockBanner />}
  </>
)

export default App
