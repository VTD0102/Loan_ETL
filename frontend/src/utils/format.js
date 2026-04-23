export const formatCurrency = (value) =>
  new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value)

export const formatDate = (dateStr) =>
  new Date(dateStr).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' })

export const formatDateTime = (dateStr) =>
  new Date(dateStr).toLocaleString('vi-VN', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })

export const STATUS_META = {
  AUTO_REJECTED:  { label: 'Tự động từ chối', color: 'danger',  bg: 'bg-danger-50',  text: 'text-danger-700',  border: 'border-danger-200'  },
  ADMIN_REJECTED: { label: 'Đã từ chối',       color: 'danger',  bg: 'bg-danger-50',  text: 'text-danger-700',  border: 'border-danger-200'  },
  PENDING_REVIEW: { label: 'Chờ xét duyệt',    color: 'warning', bg: 'bg-warning-50', text: 'text-warning-700', border: 'border-warning-200' },
  AWAITING_INFO:  { label: 'Chờ thông tin',     color: 'success', bg: 'bg-success-50', text: 'text-success-700', border: 'border-success-200' },
  INFO_SUBMITTED: { label: 'Đã nộp thông tin',  color: 'primary', bg: 'bg-primary-50', text: 'text-primary-700', border: 'border-primary-200' },
}

export const RISK_META = {
  LOW:    { label: 'Thấp',   bg: 'bg-success-50', text: 'text-success-700', border: 'border-success-200' },
  MEDIUM: { label: 'Trung bình', bg: 'bg-warning-50', text: 'text-warning-700', border: 'border-warning-200' },
  HIGH:   { label: 'Cao',    bg: 'bg-danger-50',  text: 'text-danger-700',  border: 'border-danger-200'  },
}
