const BAND_META = {
  Excellent: { text: 'text-success-700', bg: 'bg-success-50', bar: '#15803d', label: 'Xuất sắc' },
  Good: { text: 'text-primary-700', bg: 'bg-primary-50', bar: '#1d4ed8', label: 'Tốt' },
  Fair: { text: 'text-warning-700', bg: 'bg-warning-50', bar: '#b45309', label: 'Trung bình' },
  Poor: { text: 'text-danger-700', bg: 'bg-danger-50', bar: '#b91c1c', label: 'Yếu' },
}

const FEATURE_LABELS = {
  debt_to_income_ratio: 'DTI',
  loan_amount_to_income: 'Khoản vay / thu nhập',
  log_monthly_income: 'Thu nhập hàng tháng',
  payment_to_income: 'Trả nợ / thu nhập',
  high_dti_flag: 'DTI cao',
  current_debt_ratio: 'Nợ hiện tại',
  total_debt_to_income: 'Tổng nợ / thu nhập',
  max_dpd_24m: 'Quá hạn 24 tháng',
  avg_dpd_recent: 'Quá hạn gần đây',
  num_installs_dpd10: 'Kỳ trả quá hạn',
  num_bureau_records: 'Hồ sơ tín dụng',
  num_active_credit: 'Tín dụng đang hoạt động',
  total_overdue_amount: 'Tổng tiền quá hạn',
  max_credit_overdue_days: 'Ngày quá hạn cao nhất',
  has_bad_debt: 'Nợ xấu',
  total_prolongations: 'Gia hạn khoản vay',
  num_previous_loans: 'Số đơn trước',
  previous_default_rate: 'Tỷ lệ đơn rủi ro trước',
  cb_queries_30d: 'Tra cứu tín dụng 30 ngày',
  num_cb_queries: 'Số lần tra cứu tín dụng',
  is_homeowner_flag: 'Có nhà riêng',
  income_verifiable_flag: 'Thu nhập xác minh',
  years_employed: 'Số năm làm việc',
  age_years: 'Tuổi',
  education_ordinal: 'Học vấn',
  is_married_flag: 'Hôn nhân',
  employment_status_grouped: 'Tình trạng việc làm',
  occupation_type: 'Loại thu nhập',
}

const clamp = (value, min, max) => Math.min(Math.max(value, min), max)

const CreditScorePanel = ({ scorecard }) => {
  if (!scorecard) return null

  const score = Number(scorecard.credit_score || 0)
  const scorePct = clamp(((score - 300) / 550) * 100, 0, 100)
  const band = scorecard.score_band || 'Fair'
  const meta = BAND_META[band] || BAND_META.Fair
  const probability = scorecard.default_probability != null
    ? `${(scorecard.default_probability * 100).toFixed(1)}%`
    : '—'

  return (
    <div className="space-y-4">
      <div className="grid sm:grid-cols-[1.1fr_1fr] gap-4 items-stretch">
        <div className={`${meta.bg} rounded-xl p-4`}>
          <p className="text-xs text-gray-500 mb-1">Điểm tín dụng scorecard</p>
          <div className="flex items-end gap-2">
            <p className={`text-4xl font-bold ${meta.text}`}>{score}</p>
            <p className="text-sm text-gray-500 mb-1">/ 850</p>
          </div>
          <div className="mt-3 h-2 rounded-full bg-white/80 overflow-hidden">
            <div className="h-full rounded-full" style={{ width: `${scorePct}%`, backgroundColor: meta.bar }} />
          </div>
          <p className={`mt-2 text-sm font-semibold ${meta.text}`}>{meta.label}</p>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="bg-gray-50 rounded-xl p-3">
            <p className="text-xs text-gray-500 mb-1">Xác suất vỡ nợ</p>
            <p className="text-lg font-bold text-gray-900">{probability}</p>
          </div>
          <div className="bg-gray-50 rounded-xl p-3">
            <p className="text-xs text-gray-500 mb-1">Mức rủi ro</p>
            <p className="text-lg font-bold text-gray-900">{scorecard.risk_level || '—'}</p>
          </div>
        </div>
      </div>

      {scorecard.top_factors?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">Yếu tố ảnh hưởng chính</p>
          <div className="grid sm:grid-cols-3 gap-2">
            {scorecard.top_factors.map((factor, index) => (
              <div key={`${factor.feature}-${index}`} className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500 mb-1">{FEATURE_LABELS[factor.feature] || factor.feature}</p>
                <p className={`text-sm font-semibold ${
                  factor.direction === 'increases_risk' ? 'text-danger-700' : 'text-success-700'
                }`}>
                  {factor.direction === 'increases_risk' ? 'Tăng rủi ro' : 'Giảm rủi ro'}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default CreditScorePanel
