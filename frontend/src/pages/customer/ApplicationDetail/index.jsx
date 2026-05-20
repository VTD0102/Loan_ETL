import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getApplicationById, getApplicationCreditScore } from '../../../services/applications'
import { getMyCIC } from '../../../services/cic'
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
        <p className="text-sm text-success-600">Vui lòng nộp thông tin ngân hàng để hoàn tất thủ tục.</p>
        <button onClick={onSubmitInfo} className="mt-3 btn-primary text-sm">
          Nộp thông tin nhận tiền
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
        <p className="font-semibold text-primary-800">Thông tin ngân hàng đã được tiếp nhận</p>
        <p className="text-sm text-primary-600">Chúng tôi đang xử lý giải ngân và sẽ thông báo sớm.</p>
      </div>
    </div>
  </div>
)

const DisbursedBanner = ({ app, onViewContract }) => (
  <div className="rounded-xl bg-success-50 border border-success-200 p-5">
    <div className="flex items-start gap-3">
      <div className="w-10 h-10 rounded-full bg-success-100 flex items-center justify-center flex-shrink-0">
        <svg className="w-5 h-5 text-success-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      </div>
      <div className="flex-1">
        <p className="font-semibold text-success-800 mb-1">💰 Khoản vay đã được giải ngân!</p>
        <p className="text-sm text-success-700">
          Số tiền {formatCurrency(app.loan_amount)} đã được chuyển vào tài khoản của bạn.
          {app.disbursed_at && ` Thời gian: ${formatDateTime(app.disbursed_at)}`}
        </p>
        {app.contract_text && (
          <button onClick={onViewContract} className="mt-3 btn-primary text-sm flex items-center gap-2">
            📋 Xem hợp đồng vay
          </button>
        )}
      </div>
    </div>
  </div>
)

/* ── Contract Modal ─────────────────────────────── */
const ContractModal = ({ open, contractHtml, onClose }) => {
  if (!open) return null
  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[85vh] flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900">📋 Hợp đồng vay vốn</h2>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                const printWindow = window.open('', '_blank')
                printWindow.document.write(`<html><head><title>Hợp đồng vay vốn</title></head><body>${contractHtml}</body></html>`)
                printWindow.document.close()
                printWindow.print()
              }}
              className="btn-outline text-sm px-3 py-1.5 flex items-center gap-1.5"
            >
              🖨️ In
            </button>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
        <div className="overflow-y-auto flex-1 p-6">
          <div dangerouslySetInnerHTML={{ __html: contractHtml }} />
        </div>
      </div>
    </div>
  )
}

/* ── DTI Progress Bar ─────────────────────────────── */
const DTIBar = ({ dti }) => {
  if (dti == null) return null
  const pct = (dti * 100).toFixed(1)
  const color = dti > 0.4 ? 'danger' : dti > 0.25 ? 'warning' : 'success'
  return (
    <div className="bg-gray-50 rounded-lg p-3">
      <div className="flex items-center justify-between mb-1.5">
        <p className="text-xs text-gray-500">Tỷ lệ nợ/thu nhập (DTI)</p>
        <p className={`text-sm font-bold text-${color}-600`}>{pct}%</p>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-1.5">
        <div
          className={`h-1.5 rounded-full bg-${color}-500`}
          style={{ width: `${Math.min(dti * 100, 100)}%` }}
        />
      </div>
      <p className="text-[10px] text-gray-400 mt-1">
        = (trả góp hàng tháng + nợ CIC hiện tại) ÷ thu nhập
      </p>
    </div>
  )
}

/* ──────────────── Main Component ──────────────── */

const ApplicationDetailPage = () => {
  const { id }   = useParams()
  const navigate = useNavigate()
  const [app, setApp]       = useState(null)
  const [scorecard, setScorecard] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)
  const [contractOpen, setContractOpen] = useState(false)
  const [cicData, setCicData] = useState(null)
  const [cicLoading, setCicLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
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
    fetchData()
  }, [id])

  // Fetch CIC data
  useEffect(() => {
    const fetchCIC = async () => {
      try {
        const res = await getMyCIC()
        setCicData(res.data)
      } catch {
        setCicData({ found: false })
      } finally {
        setCicLoading(false)
      }
    }
    fetchCIC()
  }, [])

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

  const isCicApplied = app.feature_snapshot?.cic_applied

  const loanInfo = [
    { label: 'Số tiền vay',          value: formatCurrency(app.loan_amount)    },
    { label: 'Kỳ hạn',              value: `${app.term} tháng`                 },
    { label: 'Thu nhập hàng tháng', value: formatCurrency(app.monthly_income)  },
    { label: 'Tình trạng nhà',      value: app.is_homeowner ? 'Có nhà' : 'Không có nhà' },
    { label: 'Việc làm',            value: app.employment_status               },
    { label: 'Mục đích vay',        value: app.listing_category                },
  ]

  return (
    <>
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
          {app.status === 'DISBURSED'       && <DisbursedBanner app={app} onViewContract={() => setContractOpen(true)} />}
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
              {/* DTI bar */}
              {app.dti != null && (
                <div className="mt-4">
                  <DTIBar dti={Number(app.dti)} />
                </div>
              )}
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

          {/* CIC Section */}
          <SectionCard title="Hồ sơ tín dụng (CIC)">
            {cicLoading ? (
              <div className="flex items-center gap-2 p-4 bg-gray-50 rounded-xl">
                <LoadingSpinner size="sm" />
                <span className="text-sm text-gray-500">Đang tra cứu CIC...</span>
              </div>
            ) : cicData?.found ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2 p-3 bg-success-50 border border-success-200 rounded-lg">
                  <svg className="w-4 h-4 text-success-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p className="text-xs text-success-700">
                    <strong>Dữ liệu lấy tự động từ Trung tâm Thông tin Tín dụng (CIC)</strong> dựa trên CCCD đã đăng ký.
                    {isCicApplied && ' Dữ liệu này đã được sử dụng để đánh giá đơn vay.'}
                  </p>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-[10px] uppercase tracking-wide text-gray-400 mb-1">Điểm CIC</p>
                    <p className={`text-lg font-bold ${(cicData.record?.cic_score || 0) >= 650 ? 'text-success-600' : (cicData.record?.cic_score || 0) >= 400 ? 'text-warning-600' : 'text-danger-600'}`}>
                      {cicData.record?.cic_score ?? 'N/A'}
                    </p>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-[10px] uppercase tracking-wide text-gray-400 mb-1">Khoản vay đang mở</p>
                    <p className="text-sm font-semibold text-gray-800">{cicData.record?.total_active_loans ?? 0}</p>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-[10px] uppercase tracking-wide text-gray-400 mb-1">Tổng dư nợ</p>
                    <p className="text-sm font-semibold text-gray-800">${Number(cicData.record?.total_outstanding_debt || 0).toLocaleString()}</p>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-[10px] uppercase tracking-wide text-gray-400 mb-1">Tiền quá hạn</p>
                    <p className={`text-sm font-semibold ${Number(cicData.record?.total_overdue_amount || 0) > 0 ? 'text-danger-600' : 'text-gray-800'}`}>
                      ${Number(cicData.record?.total_overdue_amount || 0).toLocaleString()}
                    </p>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-[10px] uppercase tracking-wide text-gray-400 mb-1">Ngày quá hạn cao nhất</p>
                    <p className={`text-sm font-semibold ${(cicData.record?.max_dpd_12m || 0) > 30 ? 'text-danger-600' : 'text-gray-800'}`}>
                      {cicData.record?.max_dpd_12m ?? 0} ngày
                    </p>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-[10px] uppercase tracking-wide text-gray-400 mb-1">Nợ xấu</p>
                    <p className={`text-sm font-semibold ${cicData.record?.bad_debt_flag ? 'text-danger-600' : 'text-success-600'}`}>
                      {cicData.record?.bad_debt_flag ? 'Có' : 'Không'}
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl">
                <div className="flex items-start gap-3">
                  <svg className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <div>
                    <p className="text-sm font-semibold text-amber-800 mb-1">Chưa có hồ sơ CIC</p>
                    <p className="text-xs text-amber-700">Không tìm thấy dữ liệu tín dụng liên kết với CCCD của bạn tại Trung tâm CIC.</p>
                  </div>
                </div>
              </div>
            )}
          </SectionCard>

          {/* Timeline */}
          <SectionCard title="Trạng thái tiến trình">
            <ApplicationTimeline app={app} />
          </SectionCard>
        </div>
      </div>
    </div>

    {/* Contract Modal */}
    <ContractModal
      open={contractOpen}
      contractHtml={app?.contract_text || ''}
      onClose={() => setContractOpen(false)}
    />
    </>
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
