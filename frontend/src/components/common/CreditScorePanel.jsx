const BAND_META = {
  Excellent: { text: 'text-success-700', bg: 'bg-success-50', bar: '#15803d', label: 'Xuất sắc' },
  Good:      { text: 'text-primary-700', bg: 'bg-primary-50', bar: '#1d4ed8', label: 'Tốt' },
  Fair:      { text: 'text-warning-700', bg: 'bg-warning-50', bar: '#b45309', label: 'Trung bình' },
  Poor:      { text: 'text-danger-700',  bg: 'bg-danger-50',  bar: '#b91c1c', label: 'Yếu' },
}

const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi)

export const getScoreBand = (score) => {
  if (score >= 740) return 'Excellent'
  if (score >= 670) return 'Good'
  if (score >= 580) return 'Fair'
  return 'Poor'
}

const CreditScorePanel = ({ score }) => {
  if (!score) return null

  const s    = Number(score)
  const band = getScoreBand(s)
  const meta = BAND_META[band]
  const pct  = clamp(((s - 300) / 550) * 100, 0, 100)

  return (
    <div className={`${meta.bg} rounded-xl p-5 w-full`}>
      <p className="text-xs text-gray-500 mb-1">Điểm tín dụng</p>
      <div className="flex items-end gap-2">
        <p className={`text-4xl font-bold ${meta.text}`}>{s}</p>
        <p className="text-sm text-gray-500 mb-1">/ 850</p>
      </div>
      <div className="mt-3 h-2 rounded-full bg-white/80 overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: meta.bar }} />
      </div>
      <p className={`mt-2 text-sm font-semibold ${meta.text}`}>{meta.label}</p>
    </div>
  )
}

export default CreditScorePanel
