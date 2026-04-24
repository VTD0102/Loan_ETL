import { RiskBadge } from '../../../components/common/Badge'
import { formatCurrency } from '../../../utils/format'

/**
 * Risk Score Gauge (CSS-only semicircle)
 */
const RiskGauge = ({ score }) => {
  const pct = Math.min(Math.max(score ?? 0, 0), 100)
  const color = pct >= 60 ? '#ef4444' : pct >= 30 ? '#f59e0b' : '#22c55e'
  // Rotate from -90 (left) to +90 (right) = 180 degree arc
  const rotation = -90 + (pct / 100) * 180

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-28 h-16 overflow-hidden">
        {/* Track */}
        <div className="absolute bottom-0 left-0 w-28 h-28 rounded-full border-[10px] border-gray-100" />
        {/* Value arc — fake using box-shadow or transform trick */}
        <div
          className="absolute bottom-0 left-0 w-28 h-28 rounded-full border-[10px] border-transparent"
          style={{
            borderTopColor: color,
            borderRightColor: pct > 50 ? color : 'transparent',
            transform: `rotate(${rotation - 45}deg)`,
            transition: 'transform 0.6s ease-out',
          }}
        />
        {/* Center label */}
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 mb-1 text-center">
          <p className="text-lg font-bold text-gray-900">{pct}</p>
        </div>
      </div>
      <p className="text-xs text-gray-400 mt-1">Risk Score / 100</p>
    </div>
  )
}

/**
 * MLResultsDisplay — Section kết quả ML trong AdminApplicationDetailPage
 * Props:
 *   app {object} — application object với ML fields
 */
const MLResultsDisplay = ({ app }) => {
  if (!app) return null

  const prob      = app.default_probability
  const probPct   = prob != null ? (prob * 100).toFixed(1) : null
  const probColor = prob >= 0.4 ? 'text-danger-700' : prob >= 0.2 ? 'text-warning-700' : 'text-success-700'
  const probBg    = prob >= 0.4 ? 'bg-danger-50'   : prob >= 0.2 ? 'bg-warning-50'   : 'bg-success-50'

  const loanDiff   = app.recommended_amount && app.loan_amount
    ? app.recommended_amount - app.loan_amount : null
  const termDiff   = app.recommended_term && app.term
    ? app.recommended_term - app.term : null

  return (
    <div className="space-y-5">
      {/* Gauge + Probability row */}
      <div className="flex flex-wrap gap-4 items-start">
        {app.risk_score != null && (
          <div className="card p-4 text-center flex-shrink-0">
            <RiskGauge score={app.risk_score} />
          </div>
        )}

        <div className="flex-1 grid grid-cols-1 sm:grid-cols-2 gap-3 min-w-0">
          {/* Probability */}
          {probPct != null && (
            <div className={`rounded-xl p-4 ${probBg}`}>
              <p className="text-xs text-gray-500 mb-1">Xác suất vỡ nợ</p>
              <p className={`text-2xl font-bold ${probColor}`}>{probPct}%</p>
              <p className="text-xs text-gray-400 mt-1">
                {prob >= 0.4 ? 'Vượt ngưỡng an toàn (40%)' : 'Trong ngưỡng an toàn'}
              </p>
            </div>
          )}

          {/* Risk level */}
          {app.risk_level && (
            <div className="bg-gray-50 rounded-xl p-4">
              <p className="text-xs text-gray-500 mb-2">Mức rủi ro ML</p>
              <RiskBadge level={app.risk_level} />
            </div>
          )}
        </div>
      </div>

      {/* Recommendation comparison */}
      {(app.recommended_amount || app.recommended_term) && (
        <div className="bg-primary-50 rounded-xl p-4">
          <p className="text-xs font-semibold text-primary-700 mb-3 uppercase tracking-wide">Đề xuất của Model</p>
          <div className="grid grid-cols-2 gap-4">
            {app.recommended_amount && (
              <div>
                <p className="text-xs text-gray-500 mb-1">Hạn mức đề xuất</p>
                <p className="text-lg font-bold text-primary-700">{formatCurrency(app.recommended_amount)}</p>
                {loanDiff !== null && (
                  <p className={`text-xs mt-0.5 ${loanDiff < 0 ? 'text-danger-600' : loanDiff > 0 ? 'text-success-600' : 'text-gray-400'}`}>
                    {loanDiff < 0
                      ? `Thấp hơn yêu cầu ${formatCurrency(Math.abs(loanDiff))}`
                      : loanDiff > 0
                        ? `Cao hơn yêu cầu ${formatCurrency(loanDiff)}`
                        : 'Đúng bằng yêu cầu'}
                  </p>
                )}
              </div>
            )}
            {app.recommended_term && (
              <div>
                <p className="text-xs text-gray-500 mb-1">Kỳ hạn đề xuất</p>
                <p className="text-lg font-bold text-primary-700">{app.recommended_term} tháng</p>
                {termDiff !== null && (
                  <p className={`text-xs mt-0.5 ${termDiff !== 0 ? 'text-warning-600' : 'text-gray-400'}`}>
                    {termDiff === 0 ? 'Đúng bằng yêu cầu'
                      : termDiff > 0 ? `Dài hơn ${termDiff} tháng`
                      : `Ngắn hơn ${Math.abs(termDiff)} tháng`}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default MLResultsDisplay
