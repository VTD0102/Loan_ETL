import { useState } from 'react'

const STATUS_OPTIONS = [
  { value: '', label: 'Tất cả trạng thái' },
  { value: 'PENDING_REVIEW',  label: 'Chờ xét duyệt' },
  { value: 'AUTO_REJECTED',   label: 'Tự động từ chối' },
  { value: 'ADMIN_REJECTED',  label: 'Đã từ chối' },
  { value: 'AWAITING_INFO',   label: 'Chờ thông tin' },
  { value: 'INFO_SUBMITTED',  label: 'Đã nộp thông tin' },
]

const RISK_OPTIONS = [
  { value: '', label: 'Tất cả rủi ro' },
  { value: 'LOW',    label: 'Thấp' },
  { value: 'MEDIUM', label: 'Trung bình' },
  { value: 'HIGH',   label: 'Cao' },
]

/**
 * FilterBar — dùng trong AllApplicationsPage
 * Props:
 *   filters    {object}   — { status, risk_level, from_date, to_date }
 *   onApply    {function} — callback khi apply filters
 *   onClear    {function} — callback khi clear filters
 */
const FilterBar = ({ filters = {}, onApply, onClear }) => {
  const [local, setLocal] = useState({
    status:     filters.status     || '',
    risk_level: filters.risk_level || '',
    from_date:  filters.from_date  || '',
    to_date:    filters.to_date    || '',
  })

  const handleChange = (key, val) => setLocal((prev) => ({ ...prev, [key]: val }))

  const handleApply = () => onApply?.(local)

  const handleClear = () => {
    const cleared = { status: '', risk_level: '', from_date: '', to_date: '' }
    setLocal(cleared)
    onClear?.()
  }

  return (
    <div className="card p-4 mb-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
        {/* Status */}
        <div>
          <label className="label">Trạng thái</label>
          <select
            className="input"
            value={local.status}
            onChange={(e) => handleChange('status', e.target.value)}
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        {/* Risk Level */}
        <div>
          <label className="label">Mức rủi ro</label>
          <select
            className="input"
            value={local.risk_level}
            onChange={(e) => handleChange('risk_level', e.target.value)}
          >
            {RISK_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        {/* From date */}
        <div>
          <label className="label">Từ ngày</label>
          <input
            type="date"
            className="input"
            value={local.from_date}
            onChange={(e) => handleChange('from_date', e.target.value)}
          />
        </div>

        {/* To date */}
        <div>
          <label className="label">Đến ngày</label>
          <input
            type="date"
            className="input"
            value={local.to_date}
            onChange={(e) => handleChange('to_date', e.target.value)}
          />
        </div>
      </div>

      <div className="flex gap-2 justify-end">
        <button onClick={handleClear} className="btn-outline text-sm px-4 py-2">
          Xóa bộ lọc
        </button>
        <button onClick={handleApply} className="btn-primary text-sm px-4 py-2">
          Áp dụng
        </button>
      </div>
    </div>
  )
}

export default FilterBar
