import { useEffect, useState } from 'react'

import { buildLoanAdjustmentViewModel } from './loanAdjustment'

const Metric = ({ label, value, valueClassName = 'text-gray-900' }) => (
  <div className="rounded-lg border border-gray-200 bg-white px-3 py-2">
    <p className="text-[11px] font-medium uppercase text-gray-400">{label}</p>
    <p className={`mt-0.5 text-sm font-semibold ${valueClassName}`}>{value}</p>
  </div>
)

const LoanAdjustmentActionCard = ({
  action,
  loading = false,
  compact = false,
  onConfirm,
  onCancel,
}) => {
  const model = buildLoanAdjustmentViewModel(action)
  const [selectedIndex, setSelectedIndex] = useState(0)

  useEffect(() => {
    setSelectedIndex(0)
  }, [action])

  if (!model) return null

  const disabled = loading || model.expired
  const selectedOption = model.options[selectedIndex] || model.options[0]
  const selectedRiskLabel = selectedOption.riskLabel || model.riskLabel
  const selectedRiskClassName = selectedOption.riskClassName || model.riskClassName
  const gridClass = compact
    ? 'grid grid-cols-2 gap-2'
    : 'grid grid-cols-2 gap-2 sm:grid-cols-4'

  return (
    <div className={`rounded-lg border border-primary-200 bg-primary-50/60 shadow-sm ${compact ? 'p-3' : 'p-4'}`}>
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-primary-600 text-white">
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8V6m0 10v2m7-6a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-gray-950">Phương án nộp lại</h3>
            <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold ${selectedRiskClassName}`}>
              {selectedRiskLabel}
            </span>
          </div>
          <p className="mt-1 text-xs leading-5 text-gray-600">
            Hồ sơ mới chỉ thay đổi số tiền vay hoặc kỳ hạn theo phương án đang chọn.
          </p>
        </div>
      </div>

      <div className={`${gridClass} mt-3`}>
        <Metric label="Số tiền" value={selectedOption.amountLabel} />
        <Metric label="Kỳ hạn" value={selectedOption.termLabel} />
        <Metric label="P(default)" value={selectedOption.defaultProbabilityLabel} valueClassName="text-primary-700" />
        <Metric label="Hiệu lực" value={model.expiresInLabel} valueClassName={model.expired ? 'text-danger-700' : 'text-gray-900'} />
      </div>

      {model.options.length > 1 && (
        <div className={`mt-3 grid gap-2 ${compact ? 'grid-cols-1' : 'grid-cols-1 sm:grid-cols-3'}`}>
          {model.options.map((option, index) => {
            const selected = index === selectedIndex
            return (
              <button
                key={option.id}
                type="button"
                onClick={() => setSelectedIndex(index)}
                disabled={loading}
                className={`rounded-lg border px-3 py-2 text-left transition-colors ${
                  selected
                    ? 'border-primary-500 bg-white ring-2 ring-primary-100'
                    : 'border-gray-200 bg-white hover:border-primary-200'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-gray-900">Phương án {option.optionNumber}</span>
                  <span className={`rounded-full border px-1.5 py-0.5 text-[10px] font-semibold ${option.riskClassName}`}>
                    {option.riskLabel}
                  </span>
                </div>
                <div className="mt-1 text-sm font-bold text-gray-950">{option.amountLabel}</div>
                <div className="mt-0.5 text-xs text-gray-500">{option.termLabel} • P {option.defaultProbabilityLabel}</div>
                <div className="mt-1 text-xs leading-4 text-gray-600">{option.changeLabel}</div>
              </button>
            )
          })}
        </div>
      )}

      <div className={`mt-3 flex gap-2 ${compact ? 'flex-col' : 'flex-col sm:flex-row'}`}>
        <button
          type="button"
          onClick={() => onConfirm?.(selectedIndex)}
          disabled={disabled}
          className="btn-primary flex-1 px-3 py-2 text-xs"
        >
          Xác nhận nộp lại
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={loading}
          className="btn-outline flex-1 px-3 py-2 text-xs"
        >
          Hủy phương án
        </button>
      </div>
    </div>
  )
}

export default LoanAdjustmentActionCard
