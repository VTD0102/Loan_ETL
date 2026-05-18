import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getApplicationById, getApplicationCreditScore } from '../../../services/applications'
import { StatusBadge, RiskBadge } from '../../../components/common/Badge'
import ApplicationTimeline from '../../../components/customer/ApplicationTimeline'
import LoadingSpinner from '../../../components/common/LoadingSpinner'
import CreditScorePanel from '../../../components/common/CreditScorePanel'
import { formatCurrency, formatDateTime } from '../../../utils/format'

/* ──────────────── Sub-sections ──────────────── */

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

const SectionCard = ({ title, children }) => (
  <div className="card p-6">
    <h3 className="text-base font-semibold text-gray-900 mb-4 pb-3 border-b border-gray-100">{title}</h3>
    {children}
  </div>
)

/* ──────────────── Status-specific banners ──────────────── */

const AutoRejectedBanner = ({ app, onApply }) => (
  <div className="rounded-xl bg-danger-50 border border-danger-200 p-5">
    <div className="flex items-start gap-3">
      <div className="w-10 h-10 rounded-full bg-danger-100 flex items-center justify-center flex-shrink-0">
        <svg className="w-5 h-5 text-danger-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      </div>
      <div className="flex-1">
        <p className="font-semibold text-danger-800 mb-1">Đơn bị từ chối tự động</p>
        <p className="text-sm text-danger-600">
          Xác suất vỡ nợ: <strong>{((app.default_probability || 0) * 100).toFixed(1)}%</strong> — vượt ngưỡng cho phép (40%).
          Hãy cải thiện hồ sơ tài chính và thử lại.
        </p>
        <button onClick={onApply} className="btn-danger mt-3 text-sm">
          Nộp đơn mới
        </button>
      </div>
    </div>
  </div>
)

const PendingBanner = () => (
  <div className="rounded-xl bg-warning-50 border border-warning-200 p-5">
    <div className="flex items-center gap-3">
      <div className="w-10 h-10 rounded-full bg-warning-100 flex items-center justify-center flex-shrink-0">
        <LoadingSpinner size="sm" />
      </div>
      <div>
        <p className="font-semibold text-warning-800">Đang chờ admin xét duyệt</p>
        <p className="text-sm text-warning-600">Chúng tôi sẽ thông báo khi có kết quả. Thường trong 1–2 ngày làm việc.</p>
      </div>
    </div>
  </div>
)

const AdminRejectedBanner = ({ app, onApply }) => (
  <div className="rounded-xl bg-danger-50 border border-danger-200 p-5">
    <div className="flex items-start gap-3">
      <div className="w-10 h-10 rounded-full bg-danger-100 flex items-center justify-center flex-shrink-0">
        <svg className="w-5 h-5 text-danger-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </div>
      <div className="flex-1">
        <p className="font-semibold text-danger-800 mb-1">Đơn đã bị từ chối bởi admin</p>
        {app.admin_note && (
          <p className="text-sm text-danger-600 mb-2">Lý do: {app.admin_note}</p>
        )}
        <button onClick={onApply} className="btn-danger mt-1 text-sm">Nộp đơn mới</button>
      </div>
    </div>
  </div>
)

const AwaitingInfoBanner = ({ app, onSubmitInfo }) => (
  <div className="rounded-xl bg-success-50 border border-success-200 p-5">
    <div className="flex items-start gap-3">
      <div className="w-10 h-10 rounded-full bg-success-100 flex items-center justify-center flex-shrink-0">
        <svg className="w-5 h-5 text-success-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      </div>
      <div className="flex-1">
        <p className="font-semibold text-success-800 mb-1">🎉 Chúc mừng! Đơn đã được duyệt</p>
        <p className="text-sm text-success-700 mb-1">
          Hạn mức đề xuất: <strong>{formatCurrency(app.recommended_amount)}</strong> — Kỳ hạn: <strong>{app.recommended_term} tháng</strong>
        </p>
        <p className="text-sm text-success-600">Vui lòng nộp thông tin cá nhân để hoàn tất thủ tục.</p>
        <button onClick={onSubmitInfo} className="mt-3 btn-primary text-sm">
          Nộp thông tin cá nhân
        </button>
      </div>
    </div>
  </div>
)

const InfoSubmittedBanner = () => (
  <div className="rounded-xl bg-primary-50 border border-primary-200 p-5">
    <div className="flex items-center gap-3">
      <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center flex-shrink-0">
        <svg className="w-5 h-5 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      </div>
      <div>
        <p className="font-semibold text-primary-800">Thông tin cá nhân đã được tiếp nhận</p>
        <p className="text-sm text-primary-600">Chúng tôi đang xử lý và sẽ liên hệ với bạn sớm.</p>
      </div>
    </div>
  </div>
)

/* ──────────────── Main Component ──────────────── */

const ApplicationDetailPage = () => {
  const { id }   = useParams()
  const navigate = useNavigate()
  const [app, setApp]       = useState(null)
  const [scorecard, setScorecard] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await getApplicationById(id)
        setApp(res.data)
        try {
          const scoreRes = await getApplicationCreditScore(id)
          setScorecard(scoreRes.data)
        } catch {
          setScorecard(null)
        }
      } catch (err) {
        setError(err.response?.status === 404 ? 'Không tìm thấy đơn vay.' : 'Không thể tải dữ liệu.')
      } finally {
        setLoading(false)
      }
    }
    fetch()
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
        <button onClick={() => navigate('/dashboard')} className="btn-primary">Về Dashboard</button>
      </div>
    </div>
  )

  const loanInfo = [
    { label: 'Số tiền vay',          value: formatCurrency(app.loan_amount)    },
    { label: 'Kỳ hạn',              value: `${app.term} tháng`                 },
    { label: 'Thu nhập hàng tháng', value: formatCurrency(app.monthly_income)  },
    { label: 'DTI',                 value: `${app.dti}%`                        },
    { label: 'Tình trạng nhà',      value: app.is_homeowner ? 'Có nhà' : 'Không có nhà' },
    { label: 'Việc làm',            value: app.employment_status               },
    { label: 'Mục đích vay',        value: app.listing_category                },
  ]

  return (
    <div className="min-h-screen bg-gray-50 py-10 px-4">
      <div className="max-w-3xl mx-auto">
        {/* Back */}
        <button onClick={() => navigate('/dashboard')}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-primary-600 mb-6 transition-colors">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Quay lại Dashboard
        </button>

        {/* Header */}
        <div className="card p-6 mb-5">
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

        {/* Status-specific banner */}
        <div className="mb-5">
          {app.status === 'AUTO_REJECTED'  && <AutoRejectedBanner  app={app} onApply={() => navigate('/apply')} />}
          {app.status === 'PENDING_REVIEW' && <PendingBanner />}
          {app.status === 'ADMIN_REJECTED' && <AdminRejectedBanner app={app} onApply={() => navigate('/apply')} />}
          {app.status === 'AWAITING_INFO'  && <AwaitingInfoBanner  app={app} onSubmitInfo={() => navigate(`/submit-info/${app.id}`)} />}
          {app.status === 'INFO_SUBMITTED' && <InfoSubmittedBanner />}
        </div>

        <div className="grid gap-5">
          {/* ML Results */}
          {(app.risk_level || app.default_probability != null) && (
            <SectionCard title="Kết quả phân tích AI">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {app.risk_level && (
                  <MLStat label="Mức rủi ro" value={app.risk_level}
                    accent={app.risk_level === 'HIGH' ? 'danger' : app.risk_level === 'MEDIUM' ? 'warning' : 'success'} />
                )}
                {app.default_probability != null && (
                  <MLStat label="Xác suất vỡ nợ" value={`${(app.default_probability * 100).toFixed(1)}%`}
                    accent={app.default_probability > 0.4 ? 'danger' : app.default_probability > 0.2 ? 'warning' : 'success'} />
                )}
                {app.recommended_amount && (
                  <MLStat label="Đề xuất hạn mức" value={formatCurrency(app.recommended_amount)} accent="primary" />
                )}
                {app.recommended_term && (
                  <MLStat label="Đề xuất kỳ hạn" value={`${app.recommended_term} tháng`} accent="primary" />
                )}
              </div>
            </SectionCard>
          )}

          {scorecard && (
            <SectionCard title="Điểm tín dụng scorecard">
              <CreditScorePanel scorecard={scorecard} />
            </SectionCard>
          )}

          {/* Loan Info */}
          <SectionCard title="Thông tin đơn vay">
            <InfoGrid items={loanInfo} />
          </SectionCard>

          {/* Timeline */}
          <SectionCard title="Trạng thái tiến trình">
            <ApplicationTimeline app={app} />
          </SectionCard>
        </div>
      </div>
    </div>
  )
}

const ACCENT_MAP = {
  danger:  { bg: 'bg-danger-50',  text: 'text-danger-700'  },
  warning: { bg: 'bg-warning-50', text: 'text-warning-700' },
  success: { bg: 'bg-success-50', text: 'text-success-700' },
  primary: { bg: 'bg-primary-50', text: 'text-primary-700' },
}

const MLStat = ({ label, value, accent = 'primary' }) => {
  const { bg, text } = ACCENT_MAP[accent] || ACCENT_MAP.primary
  return (
    <div className={`${bg} rounded-xl p-3 text-center`}>
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={`text-sm font-bold ${text}`}>{value}</p>
    </div>
  )
}

export default ApplicationDetailPage
