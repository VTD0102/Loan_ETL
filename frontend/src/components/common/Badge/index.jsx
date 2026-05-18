import { STATUS_META, RISK_META } from '../../../utils/format'

export const StatusBadge = ({ status }) => {
  const meta = STATUS_META[status] || { label: status, bg: 'bg-gray-100', text: 'text-gray-700', border: 'border-gray-200' }
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${meta.bg} ${meta.text} ${meta.border}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${meta.text.replace('text-', 'bg-')}`} />
      {meta.label}
    </span>
  )
}

export const RiskBadge = ({ level }) => {
  const meta = RISK_META[level?.toUpperCase()] || { label: level, bg: 'bg-gray-100', text: 'text-gray-700', border: 'border-gray-200' }
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${meta.bg} ${meta.text} ${meta.border}`}>
      {meta.label}
    </span>
  )
}

export default StatusBadge
