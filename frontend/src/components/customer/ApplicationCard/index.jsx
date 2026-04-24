import { useNavigate } from 'react-router-dom'
import { StatusBadge } from '../../common/Badge'
import { formatCurrency, formatDate } from '../../../utils/format'

const ApplicationCard = ({ app, compact = false }) => {
  const navigate = useNavigate()

  return (
    <div className={`card overflow-hidden hover:shadow-md transition-shadow ${compact ? 'p-4' : 'p-6'}`}>
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <p className={`font-semibold text-gray-900 ${compact ? 'text-base' : 'text-lg'}`}>
            Đơn #{app.id}
          </p>
          <p className="text-sm text-gray-400 mt-0.5">Nộp ngày {formatDate(app.submitted_at)}</p>
        </div>
        <StatusBadge status={app.status} />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
        <InfoCell label="Số tiền vay" value={formatCurrency(app.loan_amount)} />
        <InfoCell label="Kỳ hạn"     value={`${app.term} tháng`} />
        {app.risk_level && <InfoCell label="Mức rủi ro" value={app.risk_level} riskLevel={app.risk_level} />}
      </div>

      <button
        onClick={() => navigate(`/application/${app.id}`)}
        className="btn-outline w-full text-sm"
      >
        Xem chi tiết
      </button>
    </div>
  )
}

const riskTextColor = { LOW: 'text-success-600', MEDIUM: 'text-warning-600', HIGH: 'text-danger-600' }

const InfoCell = ({ label, value, riskLevel }) => (
  <div className="bg-gray-50 rounded-lg p-2.5">
    <p className="text-xs text-gray-500 mb-0.5">{label}</p>
    <p className={`text-sm font-semibold ${riskLevel ? (riskTextColor[riskLevel?.toUpperCase()] || 'text-gray-800') : 'text-gray-800'}`}>
      {value}
    </p>
  </div>
)

export default ApplicationCard
