import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getAdminApplicationById } from '../../../services/admin'
import { StatusBadge, RiskBadge } from '../../../components/common/Badge'
import ApplicationTimeline from '../../../components/customer/ApplicationTimeline'
import MLResultsDisplay from '../../../components/admin/MLResultsDisplay'
import ApproveRejectButtons from '../../../components/admin/ApproveRejectButtons'
import LoadingSpinner from '../../../components/common/LoadingSpinner'
import { formatCurrency, formatDateTime } from '../../../utils/format'

/* ── Shared sub-components ──────────────────────── */

const SectionCard = ({ title, children }) => (
  <div className="card p-6">
    <h3 className="text-base font-semibold text-gray-900 mb-4 pb-3 border-b border-gray-100">{title}</h3>
    {children}
  </div>
)

const InfoGrid = ({ items }) => (
  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
    {items.map(({ label, value }) => (
      <div key={label} className="bg-gray-50 rounded-lg p-3">
        <p className="text-xs text-gray-500 mb-1">{label}</p>
        <p className="text-sm font-semibold text-gray-800">{value ?? '—'}</p>
      </div>
    ))}
  </div>
)

/* ── Main Page ──────────────────────────────────── */

const AdminApplicationDetailPage = () => {
  const { id }   = useParams()
  const navigate = useNavigate()
  const [app,     setApp]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  const fetchApp = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await getAdminApplicationById(id)
      setApp(res.data)
    } catch (err) {
      setError(err.response?.status === 404 ? 'Không tìm thấy đơn vay.' : 'Không thể tải dữ liệu.')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => { fetchApp() }, [fetchApp])

  /* After approve/reject: refresh data */
  const handleActionSuccess = () => fetchApp()

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <LoadingSpinner size="lg" />
    </div>
  )

  if (error) return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="card p-8 text-center max-w-sm w-full">
        <p className="text-danger-600 mb-4">{error}</p>
        <button onClick={() => navigate('/admin/applications')} className="btn-primary">Quay lại</button>
      </div>
    </div>
  )

  const customerInfo = [
    { label: 'User ID',  value: app.user_id },
    { label: 'Email',    value: app.user_email },
    { label: 'Username', value: app.user_username || '—' },
  ]

  const EDUCATION_LABEL = { 1: 'Tiểu học', 2: 'THCS', 3: 'THPT', 4: 'Cao đẳng / ĐH', 5: 'Sau đại học' }

  const loanInfo = [
    { label: 'Số tiền vay',         value: formatCurrency(app.loan_amount) },
    { label: 'Kỳ hạn',             value: `${app.term} tháng` },
    { label: 'Thu nhập hàng tháng', value: formatCurrency(app.monthly_income) },
    { label: 'DTI',                 value: app.dti != null ? `${app.dti}%` : '—' },
    { label: 'Tình trạng việc làm', value: app.employment_status },
    { label: 'Loại thu nhập',      value: app.occupation_type ?? '—' },
    { label: 'Năm kinh nghiệm',    value: app.years_employed != null ? `${Math.floor(app.years_employed)} năm` : '—' },
    { label: 'Tình trạng nhà',     value: app.is_homeowner ? 'Có nhà' : 'Không có nhà' },
    { label: 'Mục đích vay',       value: app.listing_category },
  ]

  const demographicInfo = [
    { label: 'Tuổi',               value: app.age_years != null ? `${app.age_years} tuổi` : '—' },
    { label: 'Trình độ học vấn',   value: EDUCATION_LABEL[app.education_ordinal] ?? '—' },
    { label: 'Tình trạng hôn nhân',value: app.is_married_flag != null ? (app.is_married_flag ? 'Đã kết hôn' : 'Độc thân') : '—' },
  ]

  const bureauInfo = [
    { label: 'Số hồ sơ tín dụng',  value: app.num_bureau_records ?? '—' },
    { label: 'Tín dụng đang hoạt động', value: app.num_active_credit ?? '—' },
    { label: 'Tổng nợ quá hạn',    value: app.total_overdue_amount != null ? formatCurrency(app.total_overdue_amount) : '—' },
    { label: 'Số ngày quá hạn (max)', value: app.max_credit_overdue_days != null ? `${app.max_credit_overdue_days} ngày` : '—' },
    { label: 'Nợ xấu',             value: app.has_bad_debt != null ? (app.has_bad_debt ? 'Có' : 'Không') : '—' },
    { label: 'Thu nhập xác minh',  value: app.income_verifiable_flag != null ? (app.income_verifiable_flag ? 'Có' : 'Không') : '—' },
  ]

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Back */}
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-primary-600 mb-6 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Quay lại
        </button>

        {/* Header */}
        <div className="card p-6 mb-5 animate-fade-in">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h1 className="text-xl font-bold text-gray-900">Đơn vay #{app.id}</h1>
              <p className="text-sm text-gray-400 mt-0.5">Nộp lúc {formatDateTime(app.submitted_at)}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <StatusBadge status={app.status} />
              {app.risk_level && <RiskBadge level={app.risk_level} />}
            </div>
          </div>
        </div>

        <div className="grid gap-5">
          {/* 1. Thông tin khách hàng */}
          <SectionCard title="Thông tin khách hàng">
            <InfoGrid items={customerInfo} />
            {app.status === 'INFO_SUBMITTED' && (
              <div className="mt-4 pt-4 border-t border-gray-100">
                <button
                  onClick={() => navigate(`/admin/personal-info/${app.id}`)}
                  className="btn-primary text-sm flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                  Xem thông tin cá nhân
                </button>
              </div>
            )}
          </SectionCard>

          {/* 2. Thông tin đơn vay */}
          <SectionCard title="Thông tin đơn vay">
            <InfoGrid items={loanInfo} />
          </SectionCard>

          {/* 3. Nhân khẩu học */}
          <SectionCard title="Nhân khẩu học">
            <InfoGrid items={demographicInfo} />
          </SectionCard>

          {/* 4. Lịch sử tín dụng */}
          <SectionCard title="Lịch sử tín dụng (Bureau)">
            <InfoGrid items={bureauInfo} />
          </SectionCard>

          {/* 5. Kết quả ML */}
          {(app.risk_level || app.default_probability != null) && (
            <SectionCard title="Kết quả phân tích ML">
              <MLResultsDisplay app={app} />
            </SectionCard>
          )}

          {/* 6. Actions — chỉ hiện khi PENDING_REVIEW */}
          {app.status === 'PENDING_REVIEW' && (
            <SectionCard title="Hành động xét duyệt">
              <p className="text-sm text-gray-500 mb-4">
                Xem xét hồ sơ và đưa ra quyết định. Hành động này không thể hoàn tác.
              </p>
              <ApproveRejectButtons appId={app.id} onSuccess={handleActionSuccess} />
            </SectionCard>
          )}

          {/* 7. Timeline */}
          <SectionCard title="Lịch sử tiến trình">
            <ApplicationTimeline app={app} />
            {/* Extra meta */}
            {app.reviewed_at && (
              <div className="mt-4 pt-4 border-t border-gray-100 grid sm:grid-cols-2 gap-3">
                <div>
                  <p className="text-xs text-gray-400">Ngày xét duyệt</p>
                  <p className="text-sm font-semibold text-gray-700">{formatDateTime(app.reviewed_at)}</p>
                </div>
                {app.reviewed_by && (
                  <div>
                    <p className="text-xs text-gray-400">Xét duyệt bởi</p>
                    <p className="text-sm font-semibold text-gray-700">{app.reviewed_by}</p>
                  </div>
                )}
                {app.admin_note && (
                  <div className="sm:col-span-2">
                    <p className="text-xs text-gray-400">Ghi chú admin</p>
                    <p className="text-sm text-danger-600 font-medium">{app.admin_note}</p>
                  </div>
                )}
              </div>
            )}
          </SectionCard>
        </div>
      </div>
    </div>
  )
}

export default AdminApplicationDetailPage
