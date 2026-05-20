import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getAdminApplicationById, getAdminApplicationCreditScore, disburseApplication } from '../../../services/admin'
import { StatusBadge, RiskBadge } from '../../../components/common/Badge'
import ApplicationTimeline from '../../../components/customer/ApplicationTimeline'
import MLResultsDisplay from '../../../components/admin/MLResultsDisplay'
import ApproveRejectButtons from '../../../components/admin/ApproveRejectButtons'
import LoadingSpinner from '../../../components/common/LoadingSpinner'
import CreditScorePanel from '../../../components/common/CreditScorePanel'
import { formatCurrency, formatDateTime } from '../../../utils/format'
import { toast } from 'react-toastify'

/* ── Shared sub-components ──────────────────────── */

const SectionCard = ({ title, children }) => (
  <div className="card p-6">
    <h3 className="text-base font-semibold text-gray-900 mb-4 pb-3 border-b border-gray-100">{title}</h3>
    {children}
  </div>
)

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

/* ── Main Page ──────────────────────────────────── */

const AdminApplicationDetailPage = () => {
  const { id }   = useParams()
  const navigate = useNavigate()
  const [app,     setApp]     = useState(null)
  const [scorecard, setScorecard] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)
  const [disbursing, setDisbursing] = useState(false)
  const [contractOpen, setContractOpen] = useState(false)

  const fetchApp = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await getAdminApplicationById(id)
      setApp(res.data)
      try {
        const scoreRes = await getAdminApplicationCreditScore(id)
        setScorecard(scoreRes.data)
      } catch {
        setScorecard(null)
      }
    } catch (err) {
      setError(err.response?.status === 404 ? 'Không tìm thấy đơn vay.' : 'Không thể tải dữ liệu.')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => { fetchApp() }, [fetchApp])

  /* After approve/reject: refresh data */
  const handleActionSuccess = () => fetchApp()

  const handleDisburse = async () => {
    if (!confirm('Xác nhận giải ngân khoản vay này? Hệ thống sẽ tự động tạo hợp đồng.')) return
    setDisbursing(true)
    try {
      await disburseApplication(id)
      toast.success('Giải ngân thành công! Hợp đồng đã được tạo.')
      fetchApp()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Giải ngân thất bại.')
    } finally {
      setDisbursing(false)
    }
  }

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <LoadingSpinner size="lg" />
    </div>
  )

  if (error) return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="card p-8 text-center max-w-sm w-full">
        <p className="text-danger-600 mb-4">{error}</p>
        <button onClick={() => navigate('/admin/applications')} className="btn-primary">Quay lại</button>
      </div>
    </div>
  )

  const customerInfo = [
    { label: 'User ID',  value: app.user_id },
    { label: 'Email',    value: app.user_email },
    { label: 'Username', value: app.user_username || '—' },
  ]

  const EDUCATION_LABEL = { 1: 'Tiểu học', 2: 'THCS', 3: 'THPT', 4: 'Cao đẳng / ĐH', 5: 'Sau đại học' }

  const loanInfo = [
    { label: 'Số tiền vay',         value: formatCurrency(app.loan_amount) },
    { label: 'Kỳ hạn',             value: `${app.term} tháng` },
    { label: 'Thu nhập hàng tháng', value: formatCurrency(app.monthly_income) },
    { label: 'DTI',                 value: app.dti != null ? `${(Number(app.dti) * 100).toFixed(1)}%` : '—' },
    { label: 'Tình trạng việc làm', value: app.employment_status },
    { label: 'Loại thu nhập',      value: app.occupation_type ?? '—' },
    { label: 'Năm kinh nghiệm',    value: app.years_employed != null ? `${Math.floor(app.years_employed)} năm` : '—' },
    { label: 'Tình trạng nhà',     value: app.is_homeowner ? 'Có nhà' : 'Không có nhà' },
    { label: 'Mục đích vay',       value: app.listing_category },
  ]

  const demographicInfo = [
    { label: 'Tuổi',               value: app.age_years != null ? `${app.age_years} tuổi` : '—' },
    { label: 'Trình độ học vấn',   value: EDUCATION_LABEL[app.education_ordinal] ?? '—' },
    { label: 'Tình trạng hôn nhân',value: app.is_married_flag != null ? (app.is_married_flag ? 'Đã kết hôn' : 'Độc thân') : '—' },
  ]

  const bureauInfo = [
    { label: 'Số hồ sơ tín dụng',  value: app.num_bureau_records ?? '—' },
    { label: 'Tín dụng đang hoạt động', value: app.num_active_credit ?? '—' },
    { label: 'Tổng dư nợ CIC',     value: app.feature_snapshot?.cic_outstanding_debt != null ? formatCurrency(app.feature_snapshot.cic_outstanding_debt) : '—' },
    { label: 'Nghĩa vụ nợ hàng tháng', value: app.feature_snapshot?.cic_monthly_installment != null ? formatCurrency(app.feature_snapshot.cic_monthly_installment) : '—' },
    { label: 'Tổng nợ quá hạn',    value: app.total_overdue_amount != null ? formatCurrency(app.total_overdue_amount) : '—' },
    { label: 'Số ngày quá hạn (max)', value: app.max_credit_overdue_days != null ? `${app.max_credit_overdue_days} ngày` : '—' },
    { label: 'Nợ xấu',             value: app.has_bad_debt != null ? (app.has_bad_debt ? 'Có' : 'Không') : '—' },
    { label: 'Thu nhập xác minh',  value: app.income_verifiable_flag != null ? (app.income_verifiable_flag ? 'Có' : 'Không') : '—' },
  ]
  
  const isCicApplied = app.feature_snapshot?.cic_applied
  const cicScore = app.feature_snapshot?.cic_score

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Back */}
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-primary-600 mb-6 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Quay lại
        </button>

        {/* Header */}
        <div className="card p-6 mb-5 animate-fade-in">
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

        <div className="grid gap-5">
          {/* 1. Thông tin khách hàng */}
          <SectionCard title="Thông tin khách hàng">
            <InfoGrid items={customerInfo} />
            {(app.status === 'INFO_SUBMITTED' || app.status === 'DISBURSED') && app.personal_info && (
              <div className="mt-4 pt-4 border-t border-gray-100">
                <h4 className="text-sm font-semibold text-gray-700 mb-3">Thông tin bổ sung</h4>
                <InfoGrid items={[
                  { label: 'Họ tên', value: app.personal_info.full_name },
                  { label: 'CCCD', value: app.personal_info.id_card_number },
                  { label: 'Điện thoại', value: app.personal_info.phone },
                  { label: 'Email', value: app.personal_info.email },
                  { label: 'Ngày sinh', value: app.personal_info.date_of_birth },
                  { label: 'Địa chỉ', value: app.personal_info.address },
                  { label: 'Số tài khoản NH', value: app.personal_info.bank_account_number || '—' },
                ]} />
              </div>
            )}
          </SectionCard>

          {/* 2. Thông tin đơn vay */}
          <SectionCard title="Thông tin đơn vay">
            <InfoGrid items={loanInfo} />
          </SectionCard>

          {/* 3. Nhân khẩu học */}
          <SectionCard title="Nhân khẩu học">
            <InfoGrid items={demographicInfo} />
          </SectionCard>

          {/* 4. Lịch sử tín dụng / CIC */}
          <SectionCard title="Lịch sử tín dụng (CIC)">
            {isCicApplied && (
              <div className="mb-4 p-3 bg-success-50 border border-success-200 rounded-lg flex items-center gap-3">
                <svg className="w-5 h-5 text-success-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <div>
                  <p className="text-sm font-semibold text-success-800">Đã xác minh qua CIC</p>
                  <p className="text-xs text-success-700">Dữ liệu bên dưới đã được tự động cập nhật từ hệ thống CIC quốc gia. Điểm CIC: {cicScore || 'N/A'}</p>
                </div>
              </div>
            )}
            <InfoGrid items={bureauInfo} />
            {app.feature_snapshot?.cic_outstanding_debt != null && (
              <p className="text-[10px] text-gray-400 mt-2">
                ¹ Tổng dư nợ CIC là số liệu từ hệ thống CIC <strong>trước khi</strong> nộp đơn vay này (chưa tính khoản vay đang chờ duyệt).
              </p>
            )}
            {/* DTI bar */}
            {app.dti != null && (
              <div className="mt-4 pt-4 border-t border-gray-100">
                <div className="flex items-center justify-between mb-1.5">
                  <p className="text-xs font-medium text-gray-600">DTI (nợ/thu nhập)</p>
                  <p className={`text-sm font-bold ${Number(app.dti) > 0.4 ? 'text-danger-600' : Number(app.dti) > 0.25 ? 'text-warning-600' : 'text-success-600'}`}>
                    {(Number(app.dti) * 100).toFixed(1)}%
                  </p>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-1.5">
                  <div
                    className={`h-1.5 rounded-full ${Number(app.dti) > 0.4 ? 'bg-danger-500' : Number(app.dti) > 0.25 ? 'bg-warning-500' : 'bg-success-500'}`}
                    style={{ width: `${Math.min(Number(app.dti) * 100, 100)}%` }}
                  />
                </div>
                <p className="text-[10px] text-gray-400 mt-1">= (trả góp hàng tháng + nợ CIC) ÷ thu nhập. &lt;25% tốt · 25-40% chấp nhận · &gt;40% rủi ro cao</p>
              </div>
            )}
          </SectionCard>

          {/* 5. Kết quả ML */}
          {(app.risk_level || app.default_probability != null) && (
            <SectionCard title="Kết quả phân tích ML">
              <MLResultsDisplay app={app} />
            </SectionCard>
          )}

          {scorecard && (
            <SectionCard title="Điểm tín dụng scorecard">
              <CreditScorePanel scorecard={scorecard} />
            </SectionCard>
          )}

          {/* 6. Actions — Duyệt (PENDING_REVIEW) */}
          {app.status === 'PENDING_REVIEW' && (
            <SectionCard title="Hành động xét duyệt">
              <p className="text-sm text-gray-500 mb-4">
                Xem xét hồ sơ và đưa ra quyết định. Hành động này không thể hoàn tác.
              </p>
              <ApproveRejectButtons appId={app.id} onSuccess={handleActionSuccess} />
            </SectionCard>
          )}

          {/* 6b. Actions — Giải ngân (INFO_SUBMITTED) */}
          {app.status === 'INFO_SUBMITTED' && (
            <SectionCard title="Xác nhận giải ngân">
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
                <p className="text-sm font-semibold text-amber-800 mb-1">⚠️ Khách hàng đã bổ sung thông tin ngân hàng</p>
                <p className="text-xs text-amber-700">
                  Vui lòng kiểm tra thông tin cá nhân và tài khoản nhận tiền ở trên trước khi xác nhận giải ngân.
                  Hệ thống sẽ tự động tạo Hợp đồng vay vốn.
                </p>
              </div>
              <button
                onClick={handleDisburse}
                disabled={disbursing}
                className="btn-primary w-full py-3 text-base flex items-center justify-center gap-2"
              >
                {disbursing && <LoadingSpinner size="sm" />}
                {disbursing ? 'Đang xử lý...' : '✅ Xác nhận giải ngân'}
              </button>
            </SectionCard>
          )}

          {/* 6c. Hợp đồng — hiển thị khi đã giải ngân */}
          {app.status === 'DISBURSED' && app.contract_text && (
            <SectionCard title="Hợp đồng vay vốn">
              <div className="bg-success-50 border border-success-200 rounded-lg p-4 mb-4">
                <p className="text-sm font-semibold text-success-800 mb-1">✅ Đã giải ngân</p>
                <p className="text-xs text-success-700">
                  Thời gian giải ngân: {app.disbursed_at ? formatDateTime(app.disbursed_at) : '—'}
                </p>
              </div>
              <button
                onClick={() => setContractOpen(true)}
                className="btn-outline w-full py-3 text-base flex items-center justify-center gap-2"
              >
                📋 Xem hợp đồng
              </button>
            </SectionCard>
          )}

          {/* 7. Timeline */}
          <SectionCard title="Lịch sử tiến trình">
            <ApplicationTimeline app={app} />
            {/* Extra meta */}
            {app.reviewed_at && (
              <div className="mt-4 pt-4 border-t border-gray-100 grid sm:grid-cols-2 gap-3">
                <div>
                  <p className="text-xs text-gray-400">Ngày xét duyệt</p>
                  <p className="text-sm font-semibold text-gray-700">{formatDateTime(app.reviewed_at)}</p>
                </div>
                {app.reviewed_by && (
                  <div>
                    <p className="text-xs text-gray-400">Xét duyệt bởi</p>
                    <p className="text-sm font-semibold text-gray-700">{app.reviewed_by}</p>
                  </div>
                )}
                {app.admin_note && (
                  <div className="sm:col-span-2">
                    <p className="text-xs text-gray-400">Ghi chú admin</p>
                    <p className="text-sm text-danger-600 font-medium">{app.admin_note}</p>
                  </div>
                )}
              </div>
            )}
          </SectionCard>
        </div>
      </div>

      {/* Contract Modal */}
      <ContractModal
        open={contractOpen}
        contractHtml={app?.contract_text || ''}
        onClose={() => setContractOpen(false)}
      />
    </div>
  )
}

export default AdminApplicationDetailPage
