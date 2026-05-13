import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getMyApplication } from '../../../services/applications'
import useAuthStore from '../../../store/authStore'
import ApplicationCard from '../../../components/customer/ApplicationCard'
import LoadingSpinner from '../../../components/common/LoadingSpinner'

const ACTIVE_STATUSES = ['PENDING_REVIEW', 'AWAITING_INFO', 'INFO_SUBMITTED']
const REJECTED_STATUSES = ['AUTO_REJECTED', 'ADMIN_REJECTED']

const EmptyState = ({ onApply }) => (
  <div className="text-center py-16 px-4">
    <div className="w-20 h-20 bg-primary-50 rounded-2xl flex items-center justify-center mx-auto mb-5">
      <svg className="w-10 h-10 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    </div>
    <h3 className="text-xl font-bold text-gray-900 mb-2">Chưa có đơn vay nào</h3>
    <p className="text-gray-500 mb-6 max-w-sm mx-auto">
      Bắt đầu bằng cách nộp đơn xin vay. AI sẽ phân tích hồ sơ và đề xuất hạn mức phù hợp trong vài giây.
    </p>
    <button onClick={onApply} className="btn-primary text-base px-8 py-3">
      Nộp đơn vay mới
    </button>
  </div>
)

const DashboardPage = () => {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const [app, setApp]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)

  useEffect(() => {
    const fetchApp = async () => {
      try {
        const res = await getMyApplication()
        setApp(res.data?.[0] ?? res.data)
      } catch (err) {
        if (err.response?.status !== 404) setError('Không thể tải dữ liệu.')
      } finally {
        setLoading(false)
      }
    }
    fetchApp()
  }, [])

  const isActive   = app && ACTIVE_STATUSES.includes(app.status)
  const isRejected = app && REJECTED_STATUSES.includes(app.status)
  const hasNoActiveApp = !app || isRejected

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-10">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">
            Xin chào, {user?.username} 👋
          </h1>
          <p className="text-gray-500 mt-1">Quản lý đơn vay và theo dõi trạng thái hồ sơ của bạn</p>
        </div>

        {/* Quick Actions */}
        <div className="grid sm:grid-cols-3 gap-4 mb-8">
          <QuickCard icon="💬" label="Tư vấn AI" desc="Chat với trợ lý AI" onClick={() => navigate('/chat')} />
          <QuickCard icon="📋" label="Nộp đơn vay" desc="Bắt đầu đăng ký khoản vay" onClick={() => navigate('/apply')} />
          <QuickCard icon="📊" label="Lịch sử đơn" desc="Xem tất cả đơn của bạn" onClick={() => navigate('/history')} />
        </div>

        {/* Main content */}
        {loading ? (
          <div className="card p-12 flex items-center justify-center">
            <LoadingSpinner size="lg" />
          </div>
        ) : error ? (
          <div className="card p-8 text-center text-danger-600">{error}</div>
        ) : (
          <>
            {hasNoActiveApp ? (
              <div className="card">
                <EmptyState onApply={() => navigate('/apply')} />
              </div>
            ) : (
              <div className="card p-6">
                <div className="flex items-center justify-between mb-5">
                  <h2 className="text-lg font-semibold text-gray-900">Đơn vay hiện tại</h2>
                </div>
                <ApplicationCard app={app} />
              </div>
            )}

            {/* Rejected history */}
            {isRejected && app && (
              <div className="mt-6 card p-6">
                <h2 className="text-base font-semibold text-gray-900 mb-4">Đơn gần đây</h2>
                <ApplicationCard app={app} compact />
                <div className="mt-4 pt-4 border-t border-gray-100 text-center">
                  <button onClick={() => navigate('/apply')} className="btn-primary">
                    Nộp đơn vay mới
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

const QuickCard = ({ icon, label, desc, onClick }) => (
  <button
    onClick={onClick}
    className="card p-4 text-left hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 cursor-pointer"
  >
    <span className="text-2xl block mb-2">{icon}</span>
    <p className="font-semibold text-gray-900 text-sm">{label}</p>
    <p className="text-xs text-gray-500 mt-0.5">{desc}</p>
  </button>
)

export default DashboardPage
