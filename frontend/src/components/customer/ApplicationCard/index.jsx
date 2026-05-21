import { useNavigate } from 'react-router-dom'
import { StatusBadge } from '../../common/Badge'
import { RISK_META, formatCurrency, formatDate } from '../../../utils/format'

const ApplicationCard = ({ app, compact = false }) => {
  const navigate = useNavigate()
  if (!app) return null

  const appCode = getApplicationCode(app.id)
  const submittedDate = formatDate(app.submitted_at)
  const amount = formatCurrency(app.loan_amount)
  const term = Number.isFinite(Number(app.term)) ? `${app.term} tháng` : 'Chưa có dữ liệu'
  const riskKey = app.risk_level?.toUpperCase()
  const riskLabel = RISK_META[riskKey]?.label || app.risk_level || null
  const recommended = app.recommended_amount ? formatCurrency(app.recommended_amount) : null
  const nextStep = getNextStep(app.status)
  const score = Number.isFinite(Number(app.risk_score)) ? `${app.risk_score}/100` : null

  return (
    <article className="card overflow-hidden hover:shadow-md transition-shadow">
      <div className={`bg-gradient-to-br from-teal-700 to-primary-700 text-white ${compact ? 'p-4' : 'p-5 sm:p-6'}`}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className={`font-semibold truncate ${compact ? 'text-sm' : 'text-base'}`}>{appCode}</p>
            <p className="text-xs text-white/75 mt-1">Nộp ngày {submittedDate}</p>
          </div>
          <StatusBadge status={app.status} />
        </div>

        <div className="mt-5">
          <p className="text-xs font-medium text-white/70">Số tiền vay</p>
          <p className={`font-bold tracking-normal mt-1 ${compact ? 'text-xl' : 'text-2xl sm:text-3xl'}`}>
            {amount}
          </p>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <SummaryPill>{term}</SummaryPill>
          {riskLabel && <SummaryPill>Rủi ro {riskLabel.toLowerCase()}</SummaryPill>}
          {recommended && <SummaryPill>Đề xuất {recommended}</SummaryPill>}
        </div>
      </div>

      <div className={compact ? 'p-4' : 'p-5'}>
        <div className="grid sm:grid-cols-2 gap-3 mb-4">
          <InfoCell label="Trạng thái tiếp theo" value={nextStep} />
          <InfoCell label="AI đánh giá" value={score || 'Chưa có dữ liệu'} riskLevel={riskKey} />
        </div>

        <button
          onClick={() => navigate(`/application/${app.id}`)}
          className="btn-outline w-full text-sm"
          disabled={!app.id}
        >
          {app.status === 'AWAITING_INFO' ? 'Tiếp tục hồ sơ' : 'Xem chi tiết'}
        </button>
      </div>
    </article>
  )
}

const riskTextColor = { LOW: 'text-success-600', MEDIUM: 'text-warning-600', HIGH: 'text-danger-600' }

const getApplicationCode = (id) => {
  if (!id) return 'Đơn vay chưa có mã'
  const text = String(id)
  const shortId = text.length > 8 ? text.slice(-8).toUpperCase() : text.toUpperCase()
  return `Đơn vay #${shortId}`
}

const getNextStep = (status) => {
  const steps = {
    PENDING_REVIEW: 'Chờ admin xét duyệt',
    AWAITING_INFO: 'Bổ sung hồ sơ',
    INFO_SUBMITTED: 'Chờ xác minh hồ sơ',
    APPROVED: 'Chờ giải ngân',
    DISBURSED: 'Đã giải ngân',
    AUTO_REJECTED: 'Có thể nộp đơn mới',
    ADMIN_REJECTED: 'Có thể nộp đơn mới',
    REJECTED: 'Có thể nộp đơn mới',
  }
  return steps[status] || 'Theo dõi trạng thái'
}

const SummaryPill = ({ children }) => (
  <span className="rounded-full bg-white/15 px-3 py-1 text-xs font-semibold text-white ring-1 ring-white/20">
    {children}
  </span>
)

const InfoCell = ({ label, value, riskLevel }) => (
  <div className="bg-gray-50 rounded-lg p-3">
    <p className="text-xs text-gray-500 mb-0.5">{label}</p>
    <p className={`text-sm font-semibold ${riskLevel ? (riskTextColor[riskLevel?.toUpperCase()] || 'text-gray-800') : 'text-gray-800'}`}>
      {value}
    </p>
  </div>
)

export default ApplicationCard
