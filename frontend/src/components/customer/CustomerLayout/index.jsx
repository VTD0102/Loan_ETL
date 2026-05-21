import { useState } from 'react'
import { Outlet, NavLink, useNavigate, Link } from 'react-router-dom'
import useAuthStore from '../../../store/authStore'

const NAV_ITEMS = [
  {
    to: '/dashboard',
    label: 'Dashboard',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M4 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
      </svg>
    ),
  },
  {
    to: '/apply',
    label: 'Tạo đơn vay',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    to: '/chat',
    label: 'Tư vấn AI',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
      </svg>
    ),
  },
]

const CustomerLayout = () => {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const [open, setOpen] = useState(false)
  const [dropdownOpen, setDropdownOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* ── Sidebar cố định ─────────────────────── */}
      <aside
        className={`
          fixed inset-y-0 left-0 z-40 w-64 bg-white border-r border-gray-200 shadow-sm
          flex flex-col transition-transform duration-300
          ${open ? 'translate-x-0' : '-translate-x-full'}
          md:translate-x-0 md:flex
        `}
      >
        {/* Logo */}
        <Link to="/dashboard" className="h-16 flex items-center gap-3 px-6 border-b border-gray-100 select-none">
          <span className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center text-white text-sm font-bold flex-shrink-0 shadow-sm">
            CI
          </span>
          <div>
            <p className="text-sm font-bold text-gray-900 leading-tight">CreditIntel</p>
            <p className="text-xs text-gray-400 leading-tight">Customer Portal</p>
          </div>
        </Link>

        {/* Nav Links */}
        <nav className="flex-1 py-6 px-3 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 ${
                  isActive
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`
              }
            >
              {item.icon}
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* Backdrop di động */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/30 backdrop-blur-sm md:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* ── Main Content Container ──────────────── */}
      <div className="flex-1 flex flex-col min-w-0 md:pl-64 h-screen">
        {/* Topbar Header */}
        <header className="h-16 sticky top-0 z-20 bg-white/95 backdrop-blur-sm border-b border-gray-200 shadow-sm flex items-center justify-between px-4 sm:px-6 flex-shrink-0">
          {/* Hamburger Mobile Button */}
          <button
            onClick={() => setOpen((o) => !o)}
            className="md:hidden p-2 rounded-lg text-gray-500 hover:bg-gray-100 transition-colors"
            aria-label="Mở menu"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          {/* Mobile Logo */}
          <div className="flex items-center gap-2 md:hidden">
            <span className="w-7 h-7 bg-primary-600 rounded-lg flex items-center justify-center text-white text-xs font-bold shadow-sm">CI</span>
            <span className="text-sm font-bold text-gray-900">CreditIntel</span>
          </div>

          {/* Right Area: Avatar Dropdown */}
          <div className="relative ml-auto">
            <button
              onClick={() => setDropdownOpen((o) => !o)}
              className="flex items-center gap-2 p-1.5 rounded-xl hover:bg-gray-100 transition-colors duration-150 focus:outline-none"
            >
              <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center border border-primary-200 shadow-sm flex-shrink-0">
                <span className="text-sm font-bold text-primary-700">
                  {user?.username?.[0]?.toUpperCase() || 'U'}
                </span>
              </div>
              <span className="hidden sm:inline text-sm font-semibold text-gray-700 truncate max-w-[120px]">
                {user?.username}
              </span>
              <svg
                className={`w-4 h-4 text-gray-400 transition-transform duration-150 ${dropdownOpen ? 'rotate-180' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {/* Dropdown Menu Overlay */}
            {dropdownOpen && (
              <>
                {/* Backdrop click-outside */}
                <div
                  className="fixed inset-0 z-30"
                  onClick={() => setDropdownOpen(false)}
                />

                <div className="absolute right-0 mt-2 w-56 rounded-xl bg-white border border-gray-200 shadow-xl z-40 py-2 animate-fade-in origin-top-right">
                  <div className="px-4 py-2 border-b border-gray-100">
                    <p className="text-xs text-gray-400">Tài khoản thường</p>
                    <p className="text-sm font-bold text-gray-800 truncate">{user?.username}</p>
                    <p className="text-xs text-gray-500 truncate mt-0.5">{user?.email}</p>
                  </div>

                  <div className="p-1">
                    <button
                      onClick={() => {
                        setDropdownOpen(false)
                        navigate('/profile')
                      }}
                      className="flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-sm text-gray-700 hover:bg-primary-50 hover:text-primary-700 transition-all duration-150"
                    >
                      <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                          d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                      </svg>
                      Thông tin cá nhân
                    </button>
                  </div>

                  <div className="border-t border-gray-100 my-1" />

                  <div className="p-1">
                    <button
                      onClick={() => {
                        setDropdownOpen(false)
                        handleLogout()
                      }}
                      className="flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-sm text-danger-600 hover:bg-danger-50 transition-all duration-150"
                    >
                      <svg className="w-4 h-4 text-danger-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                          d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                      </svg>
                      Đăng xuất
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </header>

        {/* Page Content Outlet */}
        <main className="flex-1 overflow-y-auto min-h-0">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default CustomerLayout
