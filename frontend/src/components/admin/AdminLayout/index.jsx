import { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import useAuthStore from '../../../store/authStore'

const NAV_ITEMS = [
  {
    to: '/admin/dashboard',
    label: 'Dashboard',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
      </svg>
    ),
  },
  {
    to: '/admin/pending',
    label: 'Chờ xét duyệt',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    to: '/admin/applications',
    label: 'Tất cả đơn vay',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
  },
]

const AdminLayout = () => {
  const navigate      = useNavigate()
  const user          = useAuthStore((s) => s.user)
  const logout        = useAuthStore((s) => s.logout)
  const [open, setOpen] = useState(false)
  const [dropdownOpen, setDropdownOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* ── Sidebar ─────────────────────────────── */}
      <aside
        className={`
          fixed inset-y-0 left-0 z-40 w-64 bg-white border-r border-gray-200 shadow-sm
          flex flex-col transition-transform duration-300
          ${open ? 'translate-x-0' : '-translate-x-full'}
          md:translate-x-0 md:flex
        `}
      >
        {/* Logo */}
        <div className="h-16 flex items-center gap-3 px-6 border-b border-gray-100">
          <span className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
            CI
          </span>
          <div>
            <p className="text-sm font-bold text-gray-900 leading-tight">CreditIntel</p>
            <p className="text-xs text-gray-400 leading-tight">Admin Panel</p>
          </div>
        </div>

        {/* Nav */}
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

      {/* Backdrop mobile */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/30 backdrop-blur-sm md:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* ── Main content ─────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 md:pl-64">
        {/* Top header */}
        <header className="h-16 sticky top-0 z-20 bg-white/95 backdrop-blur-sm border-b border-gray-200 shadow-sm flex items-center justify-between px-4 sm:px-6">
          {/* Hamburger */}
          <button
            onClick={() => setOpen((o) => !o)}
            className="md:hidden p-2 rounded-lg text-gray-500 hover:bg-gray-100 transition-colors"
            aria-label="Mở menu"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          {/* Logo mobile */}
          <div className="flex items-center gap-2 md:hidden">
            <span className="w-7 h-7 bg-primary-600 rounded-lg flex items-center justify-center text-white text-xs font-bold">CI</span>
            <span className="text-sm font-bold text-gray-900">Admin</span>
          </div>

          {/* Right: user info with Dropdown */}
          <div className="relative ml-auto">
            <button
              onClick={() => setDropdownOpen((o) => !o)}
              className="flex items-center gap-2 p-1.5 rounded-xl hover:bg-gray-100 transition-colors duration-150 focus:outline-none"
            >
              <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center border border-primary-200 shadow-sm flex-shrink-0">
                <span className="text-sm font-bold text-primary-700">
                  {user?.username?.[0]?.toUpperCase() || 'A'}
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

            {/* Dropdown Menu */}
            {dropdownOpen && (
              <>
                {/* Backdrop to close when clicked outside */}
                <div
                  className="fixed inset-0 z-30"
                  onClick={() => setDropdownOpen(false)}
                />
                
                <div className="absolute right-0 mt-2 w-56 rounded-xl bg-white border border-gray-200 shadow-xl z-40 py-2 animate-fade-in origin-top-right">
                  <div className="px-4 py-2 border-b border-gray-100">
                    <p className="text-xs text-gray-400">Tài khoản Admin</p>
                    <p className="text-sm font-bold text-gray-800 truncate">{user?.username}</p>
                    <p className="text-xs text-gray-500 truncate mt-0.5">{user?.email}</p>
                  </div>
                  
                  <div className="p-1">
                    <button
                      onClick={() => {
                        setDropdownOpen(false)
                        navigate('/admin/profile')
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

        {/* Page content */}
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default AdminLayout
