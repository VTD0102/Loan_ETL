import { useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import useAuthStore from '../../../store/authStore'

const Navbar = () => {
  const navigate  = useNavigate()
  const token     = useAuthStore((s) => s.token)
  const user      = useAuthStore((s) => s.user)
  const logout    = useAuthStore((s) => s.logout)
  const [open, setOpen] = useState(false)

  const handleLogout = () => {
    logout()
    setOpen(false)
    navigate('/', { replace: true })
  }

  const navLinkClass = ({ isActive }) =>
    `text-sm font-medium transition-colors ${isActive ? 'text-primary-600' : 'text-gray-600 hover:text-primary-600'}`

  return (
    <nav className="sticky top-0 z-40 bg-white/95 backdrop-blur-sm border-b border-gray-200 shadow-sm">
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2 font-bold text-primary-700 text-lg select-none">
            <span className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center text-white text-sm font-bold shadow-sm">
              CI
            </span>
            <span className="hidden sm:block">CreditIntel</span>
          </Link>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center gap-6">
            {token ? (
              <>
                <NavLink to="/dashboard" className={navLinkClass}>Dashboard</NavLink>
                <NavLink to="/chat"      className={navLinkClass}>Tư vấn AI</NavLink>
                <div className="flex items-center gap-3 ml-2 pl-4 border-l border-gray-200">
                  <span className="text-sm text-gray-500">
                    Xin chào, <span className="font-medium text-gray-800">{user?.username}</span>
                  </span>
                  <button onClick={handleLogout} className="btn-outline text-sm px-4 py-2">
                    Đăng xuất
                  </button>
                </div>
              </>
            ) : (
              <>
                <Link to="/login"    className="text-sm font-medium text-gray-600 hover:text-primary-600 transition-colors">Đăng nhập</Link>
                <Link to="/register" className="btn-primary text-sm px-5 py-2">Đăng ký</Link>
              </>
            )}
          </div>

          {/* Mobile hamburger */}
          <button
            className="md:hidden p-2 rounded-lg text-gray-600 hover:bg-gray-100 transition-colors"
            onClick={() => setOpen((o) => !o)}
            aria-label="Menu"
          >
            {open
              ? <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              : <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" /></svg>}
          </button>
        </div>

        {/* Mobile dropdown */}
        {open && (
          <div className="md:hidden border-t border-gray-100 py-3 space-y-1">
            {token ? (
              <>
                <MobileLink to="/dashboard" onClick={() => setOpen(false)}>Dashboard</MobileLink>
                <MobileLink to="/chat"      onClick={() => setOpen(false)}>Tư vấn AI</MobileLink>
                <div className="px-3 pt-3 border-t border-gray-100">
                  <p className="text-xs text-gray-400 mb-2">Đã đăng nhập: {user?.username}</p>
                  <button onClick={handleLogout} className="btn-outline w-full text-sm">Đăng xuất</button>
                </div>
              </>
            ) : (
              <>
                <MobileLink to="/login"    onClick={() => setOpen(false)}>Đăng nhập</MobileLink>
                <MobileLink to="/register" onClick={() => setOpen(false)}>Đăng ký</MobileLink>
              </>
            )}
          </div>
        )}
      </div>
    </nav>
  )
}

const MobileLink = ({ to, onClick, children }) => (
  <NavLink
    to={to}
    onClick={onClick}
    className={({ isActive }) =>
      `block px-3 py-2 rounded-lg text-sm font-medium transition-colors ${isActive ? 'bg-primary-50 text-primary-700' : 'text-gray-700 hover:bg-gray-50'}`}
  >
    {children}
  </NavLink>
)

export default Navbar
