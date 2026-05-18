const ACCENT = {
  primary: { icon: 'bg-primary-50', text: 'text-primary-700', border: 'border-primary-200', bar: 'bg-primary-600' },
  warning: { icon: 'bg-warning-50', text: 'text-warning-700', border: 'border-warning-200', bar: 'bg-warning-500' },
  success: { icon: 'bg-success-50', text: 'text-success-700', border: 'border-success-200', bar: 'bg-success-500' },
  danger:  { icon: 'bg-danger-50',  text: 'text-danger-700',  border: 'border-danger-200',  bar: 'bg-danger-500'  },
  orange:  { icon: 'bg-orange-50',  text: 'text-orange-700',  border: 'border-orange-200',  bar: 'bg-orange-500'  },
}

/**
 * SummaryCard — dùng trong AdminDashboardPage
 * Props:
 *   title   {string}   — tên card
 *   value   {number}   — giá trị hiển thị
 *   icon    {ReactNode} — SVG icon
 *   accent  {string}   — 'primary' | 'warning' | 'success' | 'danger' | 'orange'
 *   subtitle {string}  — mô tả ngắn dưới value
 *   onClick  {function} — navigate khi click
 */
const SummaryCard = ({ title, value, icon, accent = 'primary', subtitle, onClick }) => {
  const a = ACCENT[accent] || ACCENT.primary
  return (
    <div
      onClick={onClick}
      className={`relative overflow-hidden rounded-xl border bg-white p-5 shadow-sm transition-all duration-200 ${a.border} ${onClick ? 'cursor-pointer hover:-translate-y-0.5 hover:shadow-md' : ''}`}
    >
      <div className={`absolute inset-x-0 top-0 h-1 ${a.bar}`} />
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-gray-500">{title}</p>
          <p className={`mt-2 text-3xl font-bold leading-none ${a.text}`}>{value ?? '—'}</p>
          {subtitle && <p className="mt-3 text-xs leading-5 text-gray-500">{subtitle}</p>}
        </div>
        <div className={`flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl ${a.icon} ${a.text}`}>
          {icon}
        </div>
      </div>
    </div>
  )
}

export default SummaryCard
