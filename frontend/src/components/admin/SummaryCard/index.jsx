const ACCENT = {
  primary: { bg: 'bg-primary-50', icon: 'bg-primary-100', text: 'text-primary-700', badge: 'bg-primary-100 text-primary-700' },
  warning: { bg: 'bg-warning-50', icon: 'bg-warning-100', text: 'text-warning-700', badge: 'bg-warning-100 text-warning-700' },
  success: { bg: 'bg-success-50', icon: 'bg-success-100', text: 'text-success-700', badge: 'bg-success-100 text-success-700' },
  danger:  { bg: 'bg-danger-50',  icon: 'bg-danger-100',  text: 'text-danger-700',  badge: 'bg-danger-100 text-danger-700'  },
  orange:  { bg: 'bg-orange-50',  icon: 'bg-orange-100',  text: 'text-orange-700',  badge: 'bg-orange-100 text-orange-700'  },
}

/**
 * SummaryCard — dùng trong AdminDashboardPage
 * Props:
 *   title   {string}   — tên card
 *   value   {number}   — giá trị hiển thị
 *   icon    {ReactNode} — SVG icon
 *   accent  {string}   — 'primary' | 'warning' | 'success' | 'danger' | 'orange'
 *   onClick {function} — navigate khi click
 */
const SummaryCard = ({ title, value, icon, accent = 'primary', onClick }) => {
  const a = ACCENT[accent] || ACCENT.primary
  return (
    <div
      onClick={onClick}
      className={`card p-5 cursor-pointer hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 ${onClick ? '' : 'cursor-default'}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm text-gray-500 mb-1">{title}</p>
          <p className={`text-3xl font-bold ${a.text}`}>{value ?? '—'}</p>
        </div>
        <div className={`w-11 h-11 rounded-xl ${a.icon} flex items-center justify-center flex-shrink-0 ${a.text}`}>
          {icon}
        </div>
      </div>
    </div>
  )
}

export default SummaryCard
