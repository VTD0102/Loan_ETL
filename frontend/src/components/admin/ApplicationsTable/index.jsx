import { useNavigate } from 'react-router-dom'
import { StatusBadge, RiskBadge } from '../../../components/common/Badge'
import { formatCurrency, formatDate } from '../../../utils/format'

/**
 * Risk Score Progress Bar — hiển thị visual risk score 0-100
 */
const RiskScoreBar = ({ score }) => {
  if (score == null) return <span className="text-xs text-gray-400">—</span>
  const color = score >= 60 ? 'bg-danger-500' : score >= 30 ? 'bg-warning-500' : 'bg-success-500'
  return (
    <div className="flex items-center gap-2 min-w-[80px]">
      <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(score, 100)}%` }} />
      </div>
      <span className="text-xs font-medium text-gray-600 w-6 text-right">{score}</span>
    </div>
  )
}

const getFriendlyApplicationCode = (id) => {
  const compactId = String(id || '').replaceAll('-', '').toUpperCase()
  return `APP-${compactId.slice(-6) || 'NEW'}`
}

/**
 * Pagination controls
 */
const Pagination = ({ page, pages, onPrev, onNext }) => (
  <div className="flex items-center justify-between pt-4 border-t border-gray-100">
    <p className="text-sm text-gray-500">Trang {page} / {pages || 1}</p>
    <div className="flex gap-2">
      <button
        onClick={onPrev}
        disabled={page <= 1}
        className="btn-outline text-sm px-4 py-2 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        ← Trước
      </button>
      <button
        onClick={onNext}
        disabled={page >= pages}
        className="btn-outline text-sm px-4 py-2 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        Tiếp →
      </button>
    </div>
  </div>
)

/**
 * ApplicationsTable — bảng danh sách đơn vay dùng chung cho Pending và All Applications
 * Props:
 *   items      {Array}    — danh sách đơn vay
 *   showStatus {boolean}  — hiện cột Status (All Applications), ẩn ở Pending
 *   page       {number}   — trang hiện tại
 *   pages      {number}   — tổng số trang
 *   onPrev     {function}
 *   onNext     {function}
 */
const ApplicationsTable = ({ items = [], showStatus = false, page = 1, pages = 1, onPrev, onNext }) => {
  const navigate = useNavigate()

  if (items.length === 0) {
    return (
      <div className="text-center py-16 px-4">
        <div className="w-20 h-20 bg-primary-50 rounded-2xl flex items-center justify-center mx-auto mb-5">
          <svg className="w-10 h-10 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </div>
        <h3 className="text-xl font-bold text-gray-900 mb-2">Không có đơn vay nào</h3>
        <p className="text-gray-500 max-w-sm mx-auto">Danh sách trống hoặc không khớp với bộ lọc hiện tại.</p>
      </div>
    )
  }

  return (
    <div>
      {/* Desktop table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100">
              <th className="text-left py-3 px-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Mã hồ sơ</th>
              <th className="text-left py-3 px-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Khách hàng</th>
              <th className="text-right py-3 px-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Số tiền</th>
              <th className="text-center py-3 px-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Kỳ hạn</th>
              <th className="text-right py-3 px-3 text-xs font-semibold text-gray-500 uppercase tracking-wide hidden sm:table-cell">Thu nhập</th>
              <th className="text-center py-3 px-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Rủi ro</th>
              <th className="text-left py-3 px-3 text-xs font-semibold text-gray-500 uppercase tracking-wide hidden md:table-cell">Risk Score</th>
              {showStatus && (
                <th className="text-center py-3 px-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Trạng thái</th>
              )}
              <th className="text-left py-3 px-3 text-xs font-semibold text-gray-500 uppercase tracking-wide hidden lg:table-cell">Ngày nộp</th>
              <th className="py-3 px-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {items.map((app) => (
              <tr
                key={app.id}
                className="hover:bg-gray-50 transition-colors duration-100 group"
              >
                <td className="py-3 px-3">
                  <span className="inline-flex items-center rounded-md bg-gray-50 px-2 py-1 text-xs font-semibold text-gray-600 ring-1 ring-inset ring-gray-200">
                    {getFriendlyApplicationCode(app.id)}
                  </span>
                </td>
                <td className="py-3 px-3">
                  <div>
                    <p className="font-medium text-gray-900 text-sm truncate max-w-[170px]">
                      {app.user_email || app.user_username || 'Khách hàng'}
                    </p>
                  </div>
                </td>
                <td className="py-3 px-3 text-right">
                  <span className="font-semibold text-gray-800">{formatCurrency(app.loan_amount)}</span>
                </td>
                <td className="py-3 px-3 text-center">
                  <span className="text-gray-600">{app.term}th</span>
                </td>
                <td className="py-3 px-3 text-right hidden sm:table-cell">
                  <span className="text-gray-600">{formatCurrency(app.monthly_income)}</span>
                </td>
                <td className="py-3 px-3 text-center">
                  {app.risk_level
                    ? <RiskBadge level={app.risk_level} />
                    : <span className="text-xs text-gray-400">—</span>}
                </td>
                <td className="py-3 px-3 hidden md:table-cell">
                  <RiskScoreBar score={app.risk_score} />
                </td>
                {showStatus && (
                  <td className="py-3 px-3 text-center">
                    <StatusBadge status={app.status} />
                  </td>
                )}
                <td className="py-3 px-3 hidden lg:table-cell">
                  <span className="text-xs text-gray-400">{formatDate(app.submitted_at)}</span>
                </td>
                <td className="py-3 px-3">
                  <button
                    onClick={() => navigate(`/admin/application/${app.id}`)}
                    className="btn-outline text-xs px-3 py-1.5 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    Xem chi tiết
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Pagination page={page} pages={pages} onPrev={onPrev} onNext={onNext} />
    </div>
  )
}

export default ApplicationsTable
