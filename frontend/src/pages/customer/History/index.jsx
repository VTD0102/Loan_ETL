import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getMyApplication } from '../../../services/applications'
import ApplicationCard from '../../../components/customer/ApplicationCard'
import LoadingSpinner from '../../../components/common/LoadingSpinner'

const HistoryPage = () => {
  const navigate = useNavigate()
  const [apps, setApps] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const fetchApps = async () => {
      try {
        const res = await getMyApplication()
        // Ensure we handle both single object and array responses
        const data = Array.isArray(res.data) ? res.data : (res.data ? [res.data] : [])
        setApps(data)
      } catch (err) {
        setError('Không thể tải lịch sử đơn vay.')
      } finally {
        setLoading(false)
      }
    }
    fetchApps()
  }, [])

  return (
    <div className="min-h-screen bg-gray-50 py-10 px-4">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <button onClick={() => navigate('/dashboard')} className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-primary-600 mb-4 transition-colors">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Quay lại Dashboard
          </button>
          <h1 className="text-2xl font-bold text-gray-900">Lịch sử đơn vay</h1>
          <p className="text-gray-500 mt-1">Danh sách tất cả các đơn vay bạn đã gửi</p>
        </div>

        {loading ? (
          <div className="card p-12 flex items-center justify-center">
            <LoadingSpinner size="lg" />
          </div>
        ) : error ? (
          <div className="card p-8 text-center text-danger-600">{error}</div>
        ) : apps.length === 0 ? (
          <div className="card p-12 text-center text-gray-500">
            Bạn chưa có đơn vay nào.
          </div>
        ) : (
          <div className="space-y-4">
            {apps.map((app) => (
              <div key={app.id || app.application_id} className="card p-6">
                <ApplicationCard app={app} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default HistoryPage
