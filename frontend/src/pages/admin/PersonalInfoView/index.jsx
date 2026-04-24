import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getPersonalInfo } from '../../../services/admin'
import LoadingSpinner from '../../../components/common/LoadingSpinner'
import { formatDate, formatDateTime } from '../../../utils/format'

const InfoRow = ({ label, value }) => (
  <div className="bg-gray-50 rounded-lg p-4">
    <p className="text-xs text-gray-500 mb-1">{label}</p>
    <p className="text-sm font-semibold text-gray-800">{value ?? '—'}</p>
  </div>
)

const PersonalInfoViewPage = () => {
  const { id }   = useParams()
  const navigate = useNavigate()
  const [info,    setInfo]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [error,   setError]   = useState(null)

  useEffect(() => {
    const fetchInfo = async () => {
      try {
        const res = await getPersonalInfo(id)
        setInfo(res.data)
      } catch (err) {
        if (err.response?.status === 404) {
          setNotFound(true)
        } else {
          setError('Không thể tải thông tin cá nhân.')
        }
      } finally {
        setLoading(false)
      }
    }
    fetchInfo()
  }, [id])

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <LoadingSpinner size="lg" />
    </div>
  )

  if (error) return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="card p-8 text-center max-w-sm w-full">
        <p className="text-danger-600 mb-4">{error}</p>
        <button onClick={() => navigate(-1)} className="btn-primary">Quay lại</button>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Back */}
        <button
          onClick={() => navigate(`/admin/application/${id}`)}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-primary-600 mb-6 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Quay lại chi tiết đơn #{id}
        </button>

        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Thông tin cá nhân</h1>
          <p className="text-gray-500 mt-1">Hồ sơ khách hàng của đơn vay #{id}</p>
        </div>

        {notFound ? (
          /* Empty State */
          <div className="card">
            <div className="text-center py-16 px-4">
              <div className="w-20 h-20 bg-warning-50 rounded-2xl flex items-center justify-center mx-auto mb-5">
                <svg className="w-10 h-10 text-warning-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">Chưa có thông tin cá nhân</h3>
              <p className="text-gray-500 mb-6 max-w-sm mx-auto">
                Khách hàng chưa nộp thông tin cá nhân cho đơn vay này.
              </p>
              <button
                onClick={() => navigate(`/admin/application/${id}`)}
                className="btn-primary"
              >
                Quay lại chi tiết đơn
              </button>
            </div>
          </div>
        ) : (
          /* Personal Info Card */
          <div className="card p-6 animate-fade-in">
            <div className="flex items-center gap-3 mb-6 pb-5 border-b border-gray-100">
              <div className="w-12 h-12 rounded-full bg-primary-100 flex items-center justify-center flex-shrink-0">
                <svg className="w-6 h-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </div>
              <div>
                <h2 className="text-lg font-bold text-gray-900">{info?.full_name}</h2>
                <p className="text-sm text-gray-500">Thông tin read-only</p>
              </div>
            </div>

            <div className="grid sm:grid-cols-2 gap-3">
              <InfoRow label="Họ và tên"             value={info?.full_name} />
              <InfoRow label="CCCD / CMND"           value={info?.id_card_number} />
              <InfoRow label="Số điện thoại"        value={info?.phone} />
              <InfoRow label="Email"                  value={info?.email} />
              <InfoRow label="Ngày sinh"             value={info?.date_of_birth ? formatDate(info.date_of_birth) : null} />
              <InfoRow label="Ngày nộp"              value={info?.submitted_at ? formatDateTime(info.submitted_at) : null} />
              <div className="sm:col-span-2">
                <InfoRow label="Địa chỉ"             value={info?.address} />
              </div>
            </div>

            <div className="mt-5 pt-4 border-t border-gray-100 flex justify-end">
              <button
                onClick={() => navigate(`/admin/application/${id}`)}
                className="btn-outline"
              >
                ← Quay lại chi tiết đơn
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default PersonalInfoViewPage
