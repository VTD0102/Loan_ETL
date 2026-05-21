import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getMyApplication } from '../../../services/applications'
import useAuthStore from '../../../store/authStore'
import LoadingSpinner from '../../../components/common/LoadingSpinner'
import { StatusBadge } from '../../../components/common/Badge'
import { formatCurrency, formatDate } from '../../../utils/format'

const FILTER_OPTIONS = [
  { key: 'ALL', label: 'Tất cả' },
  { key: 'PENDING_REVIEW', label: 'Chờ xét duyệt' },
  { key: 'AWAITING_INFO', label: 'Cần bổ sung' },
  { key: 'INFO_SUBMITTED', label: 'Đã nộp thông tin' },
  { key: 'REJECTED', label: 'Bị từ chối' },
  { key: 'APPROVED', label: 'Đã duyệt' },
]

const SORT_OPTIONS = [
  { key: 'NEWEST', label: 'Mới nhất' },
  { key: 'OLDEST', label: 'Cũ nhất' },
]

const EmptyState = ({ onApply }) => (
  <div className="text-center py-16 px-4">
    <div className="w-20 h-20 bg-primary-50 rounded-2xl flex items-center justify-center mx-auto mb-5 border border-primary-100 shadow-sm">
      <svg className="w-10 h-10 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    </div>
    <h3 className="text-xl font-bold text-gray-900 mb-2">Chưa có đơn vay nào</h3>
    <p className="text-gray-500 mb-6 max-w-sm mx-auto">
      Bắt đầu bằng cách nộp đơn xin vay. AI sẽ phân tích hồ sơ và đề xuất hạn mức phù hợp trong vài giây.
    </p>
    <button onClick={onApply} className="btn-primary text-base px-8 py-3 shadow-md hover:shadow-lg transition-shadow">
      Nộp đơn vay mới
    </button>
  </div>
)

const DashboardPage = () => {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const [apps, setApps] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeFilter, setActiveFilter] = useState('ALL')
  const [activeSort, setActiveSort] = useState('NEWEST')
  const [filterDropdownOpen, setFilterDropdownOpen] = useState(false)

  useEffect(() => {
    const fetchApps = async () => {
      try {
        const res = await getMyApplication()
        const data = res.data || []
        setApps(Array.isArray(data) ? data : [data])
      } catch (err) {
        if (err.response?.status !== 404) {
          setError('Không thể tải dữ liệu đơn vay.')
        }
      } finally {
        setLoading(false)
      }
    }
    fetchApps()
  }, [])

  // Bộ lọc đơn vay động
  const filteredApps = apps.filter((app) => {
    if (activeFilter === 'ALL') return true
    if (activeFilter === 'REJECTED') {
      return ['AUTO_REJECTED', 'ADMIN_REJECTED', 'REJECTED'].includes(app.status)
    }
    if (activeFilter === 'APPROVED') {
      return ['APPROVED', 'DISBURSED'].includes(app.status)
    }
    return app.status === activeFilter
  })

  // Sắp xếp đơn vay theo ngày nộp
  const sortedAndFilteredApps = [...filteredApps].sort((a, b) => {
    const timeA = new Date(a.submitted_at).getTime()
    const timeB = new Date(b.submitted_at).getTime()
    if (activeSort === 'NEWEST') {
      return timeB - timeA // Mới nhất lên đầu
    } else {
      return timeA - timeB // Cũ nhất lên đầu
    }
  })

  const activeFilterLabel = FILTER_OPTIONS.find((opt) => opt.key === activeFilter)?.label || 'Tất cả'
  const activeSortLabel = SORT_OPTIONS.find((opt) => opt.key === activeSort)?.label || 'Mới nhất'

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10 animate-fade-in">
        {/* Header */}
        <div className="mb-8 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-extrabold text-gray-900 tracking-tight">
              Xin chào, {user?.username} 👋
            </h1>
            <p className="text-gray-500 mt-1">Quản lý đơn vay và theo dõi trạng thái hồ sơ của bạn</p>
          </div>
        </div>

        {/* Quick Actions (Chỉ có 2 phần: Tư vấn AI và Nộp đơn) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-10">
          <QuickCard
            icon={
              <div className="w-10 h-10 rounded-xl bg-primary-100 flex items-center justify-center text-xl shadow-sm text-primary-700">
                💬
              </div>
            }
            label="Tư vấn AI"
            desc="Trò chuyện với trợ lý AI hỗ trợ tài chính 24/7"
            onClick={() => navigate('/chat')}
          />
          <QuickCard
            icon={
              <div className="w-10 h-10 rounded-xl bg-success-100 flex items-center justify-center text-xl shadow-sm text-success-700">
                📋
              </div>
            }
            label="Nộp đơn vay mới"
            desc="Điền thông tin và nhận phân tích hạn mức vay trong vài giây"
            onClick={() => navigate('/apply')}
          />
        </div>

        {/* Main Content Area */}
        <div>
          <div className="mb-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <h2 className="text-lg font-bold text-gray-900">Danh sách đơn vay</h2>
              <p className="text-xs text-gray-400 mt-0.5">Lọc và tra cứu thông tin chi tiết các hồ sơ vay</p>
            </div>

            {/* Bộ lọc duy nhất dạng Dropdown */}
            <div className="relative">
              <button
                onClick={() => setFilterDropdownOpen(!filterDropdownOpen)}
                className="btn-outline text-xs px-4 py-2 flex items-center gap-2 hover:bg-gray-50 focus:outline-none rounded-xl"
              >
                <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
                </svg>
                <span>Bộ lọc & Sắp xếp: {activeFilterLabel} ({activeSortLabel})</span>
                <svg className={`w-3.5 h-3.5 text-gray-400 transition-transform duration-150 ${filterDropdownOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {filterDropdownOpen && (
                <>
                  <div className="fixed inset-0 z-30" onClick={() => setFilterDropdownOpen(false)} />
                  <div className="absolute right-0 mt-2 w-64 bg-white border border-gray-200 shadow-xl rounded-xl z-40 p-2.5 animate-fade-in origin-top-right">
                    {/* Trạng thái Section */}
                    <div className="mb-3">
                      <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider px-2.5 mb-1.5">Trạng thái hồ sơ</p>
                      <div className="space-y-0.5">
                        {FILTER_OPTIONS.map((opt) => {
                          const isActive = activeFilter === opt.key
                          return (
                            <button
                              key={opt.key}
                              onClick={() => {
                                setActiveFilter(opt.key)
                                setFilterDropdownOpen(false)
                              }}
                              className={`w-full text-left px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center justify-between transition-colors ${
                                isActive
                                  ? 'bg-primary-50 text-primary-700'
                                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                              }`}
                            >
                              <span>{opt.label}</span>
                              {isActive && <span className="text-primary-600">✓</span>}
                            </button>
                          )
                        })}
                      </div>
                    </div>

                    <div className="border-t border-gray-100 my-2" />

                    {/* Sắp xếp Section */}
                    <div>
                      <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider px-2.5 mb-1.5">Sắp xếp theo ngày nộp</p>
                      <div className="space-y-0.5">
                        {SORT_OPTIONS.map((opt) => {
                          const isActive = activeSort === opt.key
                          return (
                            <button
                              key={opt.key}
                              onClick={() => {
                                setActiveSort(opt.key)
                                setFilterDropdownOpen(false)
                              }}
                              className={`w-full text-left px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center justify-between transition-colors ${
                                isActive
                                  ? 'bg-primary-50 text-primary-700'
                                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                              }`}
                            >
                              <span>{opt.label}</span>
                              {isActive && <span className="text-primary-600">✓</span>}
                            </button>
                          )
                        })}
                      </div>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>

          {loading ? (
            <div className="card p-16 flex items-center justify-center bg-white border border-gray-200">
              <LoadingSpinner size="lg" />
            </div>
          ) : error ? (
            <div className="card p-8 text-center text-danger-600 bg-white border border-danger-100">{error}</div>
          ) : apps.length === 0 ? (
            <div className="card bg-white border border-gray-200">
              <EmptyState onApply={() => navigate('/apply')} />
            </div>
          ) : sortedAndFilteredApps.length === 0 ? (
            <div className="card p-16 text-center text-gray-500 bg-white border border-gray-200">
              <svg className="w-12 h-12 text-gray-300 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-sm font-semibold text-gray-700">Không tìm thấy đơn vay nào</p>
              <p className="text-xs text-gray-400 mt-1">Vui lòng thử chọn trạng thái bộ lọc khác.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {(() => {
                // Sắp xếp bản sao danh sách đơn vay theo trình tự thời gian tăng dần để có STT cố định, nhất quán
                const sortedForSTT = [...apps].sort((a, b) => new Date(a.submitted_at) - new Date(b.submitted_at))

                return sortedAndFilteredApps.map((app) => {
                  const stt = sortedForSTT.findIndex((a) => a.id === app.id) + 1
                  return (
                    <div
                      key={app.id}
                      onClick={() => navigate(`/application/${app.id}`)}
                      className="group flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 p-4 bg-white border border-gray-200 hover:border-primary-300 hover:shadow-md hover:-translate-y-0.5 rounded-xl transition-all duration-200 cursor-pointer"
                    >
                      <div className="flex items-center gap-4 min-w-0">
                        {/* STT Badge */}
                        <div className="w-10 h-10 rounded-xl bg-primary-50 flex items-center justify-center flex-shrink-0 text-primary-700 font-bold border border-primary-100 text-sm group-hover:scale-105 transition-transform duration-200" title="Số thứ tự đơn">
                          {stt}
                        </div>
                        {/* Loan Info */}
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                            <span className="font-bold text-gray-900 text-sm sm:text-base group-hover:text-primary-600 transition-colors">
                              Đơn số {stt}
                            </span>
                            <span className="text-xs text-gray-300">|</span>
                            <span className="text-sm font-semibold text-primary-600">
                              {formatCurrency(app.loan_amount)}
                            </span>
                            <span className="text-xs text-gray-400">•</span>
                            <span className="text-xs font-medium text-gray-500">{app.term} tháng</span>
                          </div>
                          <p className="text-xs text-gray-400 mt-1">Nộp ngày {formatDate(app.submitted_at)}</p>
                        </div>
                      </div>

                      {/* Status, Risk and Arrow */}
                      <div className="flex items-center justify-between sm:justify-end gap-3.5 w-full sm:w-auto border-t sm:border-t-0 pt-3 sm:pt-0 border-gray-50">
                        {app.risk_level && (
                          <span className="text-xs font-semibold px-2 py-1 bg-gray-50 border border-gray-100 rounded text-gray-500">
                            Rủi ro: {app.risk_level}
                          </span>
                        )}
                        <div className="flex items-center gap-3">
                          <StatusBadge status={app.status} />
                          <svg className="w-5 h-5 text-gray-300 group-hover:text-primary-500 group-hover:translate-x-0.5 transition-all duration-200 hidden sm:block" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                          </svg>
                        </div>
                      </div>
                    </div>
                  )
                })
              })()}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

const QuickCard = ({ icon, label, desc, onClick }) => (
  <button
    onClick={onClick}
    className="card p-5 text-left bg-white border border-gray-200 hover:border-primary-300 hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 flex items-start gap-4 w-full cursor-pointer group"
  >
    <div className="flex-shrink-0 group-hover:scale-110 transition-transform duration-200">
      {icon}
    </div>
    <div className="min-w-0 flex-1">
      <p className="font-bold text-gray-900 text-sm group-hover:text-primary-600 transition-colors">{label}</p>
      <p className="text-xs text-gray-500 mt-1 leading-relaxed">{desc}</p>
    </div>
  </button>
)

export default DashboardPage
