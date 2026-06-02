import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { toast } from 'react-toastify'
import { evaluateApplication, confirmApplication } from '../../../services/applications'
import { sendMessage as sendChatMessage } from '../../../services/chat'
import { getMyCIC } from '../../../services/cic'
import RejectedRagAdvisorModal from '../../../components/customer/RejectedRagAdvisorModal'
import Modal from '../../../components/common/Modal'
import LoadingSpinner from '../../../components/common/LoadingSpinner'
import { formatCurrency } from '../../../utils/format'

// ── Constants ──────────────────────────────────────────────────────────────
const TERM_OPTIONS = [12, 24, 36, 48, 60]

const EMPLOYMENT_OPTIONS = [
  'Employed', 'Self-employed', 'Retired', 'Not employed', 'Other',
]

const CATEGORY_OPTIONS = [
  'Debt Consolidation', 'Home Improvement', 'Business', 'Personal Loan',
  'Auto/Vehicle', 'Medical/Dental', 'Education', 'Other',
]

const EDUCATION_OPTIONS = [
  { value: 1, label: 'Dưới THPT' },
  { value: 2, label: 'THPT' },
  { value: 3, label: 'Cao đẳng' },
  { value: 4, label: 'Đại học' },
  { value: 5, label: 'Sau đại học' },
]

const INCOME_TYPE_OPTIONS = [
  { value: 'EMPLOYED', label: 'Nhân viên hưởng lương' },
  { value: 'PRIVATE_SECTOR_EMPLOYEE', label: 'Nhân viên khu vực tư nhân' },
  { value: 'SALARIED_GOVT', label: 'Công chức / nhà nước' },
  { value: 'SELFEMPLOYED', label: 'Tự kinh doanh' },
  { value: 'RETIRED_PENSIONER', label: 'Hưu trí' },
  { value: 'OTHER', label: 'Khác / chưa xác định' },
]

const FIELD_CLASS =
  'w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-900 shadow-sm outline-none transition-all duration-150 placeholder:text-gray-400 focus:border-primary-400 focus:ring-4 focus:ring-primary-50 disabled:bg-gray-50'

const SELECT_CLASS =
  'w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-900 shadow-sm outline-none transition-all duration-150 focus:border-primary-400 focus:ring-4 focus:ring-primary-50'

const DTI_STYLES = {
  success: { text: 'text-success-600', bar: 'bg-success-500' },
  warning: { text: 'text-warning-600', bar: 'bg-warning-500' },
  danger:  { text: 'text-danger-600',  bar: 'bg-danger-500' },
}

const createEmptyRejectedAdvisor = () => ({
  sessionId: null,
  pendingAction: null,
  ragResponse: '',
  submitting: false,
  submittedMessage: '',
})

// ── Helper components ──────────────────────────────────────────────────────
const FieldRow = ({ label, hint, error, children }) => (
  <div className="space-y-1.5">
    <div className="flex items-center gap-1.5 mb-1.5">
      <label className="text-sm font-semibold text-gray-800">{label}</label>
      {hint && (
        <span className="group relative">
          <svg className="w-4 h-4 text-gray-400 cursor-help" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="invisible group-hover:visible absolute left-5 -top-1 w-56 text-xs bg-gray-900 text-white rounded-lg px-3 py-2 z-10 shadow-lg">
            {hint}
          </span>
        </span>
      )}
    </div>
    {children}
    {error && <p className="error-msg">{error}</p>}
  </div>
)

const SectionTitle = ({ title }) => (
  <div className="flex items-center gap-3 pt-3 pb-1">
    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary-50 text-primary-700 ring-1 ring-primary-100">
      <SectionIcon title={title} />
    </div>
    <div>
      <h2 className="text-sm font-bold text-gray-900">{title}</h2>
      <p className="text-xs text-gray-500">{SECTION_DESCRIPTIONS[title]}</p>
    </div>
    <div className="ml-auto hidden h-px flex-1 bg-gray-100 sm:block" />
  </div>
)

const SECTION_DESCRIPTIONS = {
  'Thông tin tài chính': 'Khoản vay, thu nhập và mục đích sử dụng vốn.',
  'Thông tin cá nhân': 'Các dữ liệu nền giúp mô hình đánh giá đúng hồ sơ.',
  'Hồ sơ tín dụng (CIC)': 'Dữ liệu tín dụng được tra cứu tự động theo CCCD.',
}

const SectionIcon = ({ title }) => {
  const path = title === 'Thông tin tài chính'
    ? 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8v2m0 14v2m8-8h-2M6 12H4m13.657-5.657-1.414 1.414M7.757 16.243l-1.414 1.414m0-11.314 1.414 1.414m8.486 8.486 1.414 1.414'
    : title === 'Thông tin cá nhân'
      ? 'M15.75 7.5a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.5 19.5a7.5 7.5 0 0115 0'
      : 'M9 12l2 2 4-4m5-2.5V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2h12a2 2 0 002-2v-1.5'

  return (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={path} />
    </svg>
  )
}



// ── Main Apply page ────────────────────────────────────────────────────────
const ApplyPage = () => {
  const navigate  = useNavigate()
  const formRef = useRef(null)
  const [loading, setLoading]         = useState(false)
  const [modal, setModal]             = useState(null)  // { type: 'rejected'|'success', data }
  const [rejectedAdvisor, setRejectedAdvisor] = useState(createEmptyRejectedAdvisor)
  const [cicData, setCicData]         = useState(null)     // { found, record }
  const [cicLoading, setCicLoading]   = useState(true)

  // Fetch CIC on mount
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

  const { register, handleSubmit, setFocus, setValue, formState: { errors } } = useForm({
    defaultValues: {
      term: 36,
      employment_status: 'Employed',
      listing_category: 'Debt Consolidation',
      occupation_type: 'EMPLOYED',
      years_employed: 0,
      is_homeowner: 'false',
      is_married_flag: 'false',
      education_ordinal: 4,
    },
  })

  const buildPayload = (data) => ({
    monthly_income:          parseFloat(data.monthly_income),
    loan_amount:             parseFloat(data.loan_amount),
    term:                    parseInt(data.term),
    employment_status:       data.employment_status,
    is_homeowner:            data.is_homeowner === 'true' || data.is_homeowner === true,
    listing_category:        data.listing_category,
    occupation_type:         data.occupation_type,
    years_employed:          parseFloat(data.years_employed) || 0,
    age_years:               parseInt(data.age_years),
    education_ordinal:       parseInt(data.education_ordinal),
    is_married_flag:         data.is_married_flag === 'true' || data.is_married_flag === true,
  })

  const onSubmit = async (data) => {
    setLoading(true)
    try {
      const payload = buildPayload(data)
      const res   = await evaluateApplication(payload)
      const result = res.data

      if (result.status === 'AUTO_REJECTED') {
        let advisorState = createEmptyRejectedAdvisor()
        try {
          const chatRes = await sendChatMessage({
            message: 'Đề xuất 3 khoản vay phù hợp cho hồ sơ bị từ chối',
          })
          advisorState = {
            ...advisorState,
            sessionId: chatRes.data?.session_id || null,
            pendingAction: chatRes.data?.pending_action || null,
            ragResponse: chatRes.data?.response || '',
          }
        } catch (chatErr) {
          advisorState.ragResponse = chatErr.response?.data?.detail || 'Chưa thể tải phương án RAG. Vui lòng thử lại sau ít phút.'
        }
        setRejectedAdvisor(advisorState)
        setModal({ type: 'rejected', data: result })
        return
      }

      // For any status other than AUTO_REJECTED (e.g. APPROVED or PENDING_REVIEW):
      // Auto-confirm the application directly and show the success modal!
      const confirmRes = await confirmApplication({ ...payload, application_id: result.application_id })
      setModal({ type: 'success', data: confirmRes.data })
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Nộp đơn thất bại. Vui lòng thử lại.')
    } finally {
      setLoading(false)
    }
  }

  const handleRejectedAdvisorConfirm = async (selectedIndex) => {
    if (!rejectedAdvisor.sessionId) {
      toast.error('Chưa có phiên RAG để xác nhận phương án. Vui lòng thử lại.')
      return
    }

    setRejectedAdvisor((prev) => ({ ...prev, submitting: true }))
    try {
      const res = await sendChatMessage({
        message: `Xác nhận phương án ${selectedIndex + 1}`,
        session_id: rejectedAdvisor.sessionId,
      })
      setRejectedAdvisor((prev) => ({
        ...prev,
        pendingAction: res.data?.pending_action || null,
        submittedMessage: res.data?.response || 'Đã nộp lại hồ sơ mới.',
      }))
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Không thể nộp lại phương án. Vui lòng thử lại.')
    } finally {
      setRejectedAdvisor((prev) => ({ ...prev, submitting: false }))
    }
  }

  const handleRejectedAdvisorClose = async () => {
    if (rejectedAdvisor.submitting) return

    if (rejectedAdvisor.sessionId && rejectedAdvisor.pendingAction && !rejectedAdvisor.submittedMessage) {
      try {
        await sendChatMessage({ message: 'Hủy', session_id: rejectedAdvisor.sessionId })
      } catch {
        // Closing the modal should not be blocked by chat cleanup failure.
      }
    }
    setModal(null)
    setRejectedAdvisor(createEmptyRejectedAdvisor())
  }

  const handleRejectedAdvisorSubmitAnother = async (selectedIndex = 0) => {
    const proposals = rejectedAdvisor.pendingAction?.proposals
    const selectedProposal = Array.isArray(proposals)
      ? proposals[selectedIndex] || rejectedAdvisor.pendingAction?.proposal
      : rejectedAdvisor.pendingAction?.proposal

    if (selectedProposal?.loan_amount) {
      setValue('loan_amount', Number(selectedProposal.loan_amount), {
        shouldDirty: true,
        shouldTouch: true,
        shouldValidate: true,
      })
    }
    if (selectedProposal?.term) {
      setValue('term', String(selectedProposal.term), {
        shouldDirty: true,
        shouldTouch: true,
        shouldValidate: true,
      })
    }

    await handleRejectedAdvisorClose()
    requestAnimationFrame(() => {
      formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      setFocus('loan_amount')
    })
  }

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-10">
      <div className="mx-auto max-w-3xl">
        {/* Header */}
        <div className="mb-8">
          <button onClick={() => navigate('/dashboard')} className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-primary-600 mb-4 transition-colors">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Quay lại Dashboard
          </button>
          <div className="rounded-2xl border border-primary-100 bg-white p-6 shadow-sm">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="mb-2 inline-flex rounded-full bg-primary-50 px-3 py-1 text-xs font-semibold text-primary-700 ring-1 ring-primary-100">
                  AI Credit Review
                </p>
                <h1 className="text-2xl font-bold text-gray-900">Nộp đơn vay mới</h1>
                <p className="mt-1 max-w-xl text-sm text-gray-500">
                  Nhập thông tin tài chính và hồ sơ cá nhân. Hệ thống sẽ kiểm tra CIC và đánh giá rủi ro tự động.
                </p>
              </div>
              <div className="rounded-xl bg-gray-50 px-4 py-3 ring-1 ring-gray-100">
                <p className="text-xs font-medium text-gray-500">Đơn vị tiền tệ</p>
                <p className="text-sm font-bold text-gray-900">USD</p>
              </div>
            </div>
          </div>
        </div>

        <div className="card overflow-hidden">
          <form ref={formRef} onSubmit={handleSubmit(onSubmit)} className="space-y-7 p-6 sm:p-8" noValidate>

            {/* ── Section 1: Tài chính ─────────────────────────── */}
            <SectionTitle title="Thông tin tài chính" />
            <div className="grid sm:grid-cols-2 gap-5">
              <FieldRow label="Thu nhập hàng tháng (USD)" error={errors.monthly_income?.message}>
                <input type="number" step="0.01" min="1" placeholder="5,000"
                  className={`${FIELD_CLASS} ${errors.monthly_income ? 'input-error' : ''}`}
                  {...register('monthly_income', { required: 'Bắt buộc', min: { value: 1, message: 'Phải > 0' } })} />
              </FieldRow>
              <FieldRow label="Số tiền muốn vay (USD)" error={errors.loan_amount?.message}>
                <input type="number" step="0.01" min="500" placeholder="10,000"
                  className={`${FIELD_CLASS} ${errors.loan_amount ? 'input-error' : ''}`}
                  {...register('loan_amount', { required: 'Bắt buộc', min: { value: 500, message: 'Tối thiểu $500' }, max: { value: 150000, message: 'Tối đa $150,000' } })} />
              </FieldRow>
            </div>

            <div className="grid sm:grid-cols-2 gap-5">
              <FieldRow label="Kỳ hạn vay" error={errors.term?.message}>
                <select className={`${SELECT_CLASS} ${errors.term ? 'input-error' : ''}`} {...register('term', { required: 'Bắt buộc' })}>
                  {TERM_OPTIONS.map(t => <option key={t} value={t}>{t} tháng</option>)}
                </select>
              </FieldRow>
              <FieldRow label="Mục đích vay" error={errors.listing_category?.message}>
                <select className={`${SELECT_CLASS} ${errors.listing_category ? 'input-error' : ''}`} {...register('listing_category', { required: 'Bắt buộc' })}>
                  {CATEGORY_OPTIONS.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </FieldRow>
            </div>

            <div className="grid sm:grid-cols-2 gap-5">
              <FieldRow label="Có nhà riêng không?" error={errors.is_homeowner?.message}>
                <select className={`${SELECT_CLASS} ${errors.is_homeowner ? 'input-error' : ''}`} {...register('is_homeowner', { required: 'Bắt buộc' })}>
                  <option value="false">Không</option>
                  <option value="true">Có</option>
                </select>
              </FieldRow>
            </div>

            {/* ── Section 2: Thông tin cá nhân ─────────────────── */}
            <SectionTitle title="Thông tin cá nhân" />
            <div className="grid sm:grid-cols-2 gap-5">
              <FieldRow label="Tình trạng việc làm" error={errors.employment_status?.message}>
                <select className={`${SELECT_CLASS} ${errors.employment_status ? 'input-error' : ''}`} {...register('employment_status', { required: 'Bắt buộc' })}>
                  {EMPLOYMENT_OPTIONS.map(o => <option key={o} value={o}>{o}</option>)}
                </select>
              </FieldRow>
              <FieldRow label="Loại thu nhập" error={errors.occupation_type?.message}>
                <select className={`${SELECT_CLASS} ${errors.occupation_type ? 'input-error' : ''}`} {...register('occupation_type', { required: 'Bắt buộc' })}>
                  {INCOME_TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </FieldRow>
            </div>

            <div className="grid sm:grid-cols-2 gap-5">
              <FieldRow label="Số năm kinh nghiệm làm việc" hint="0 nếu chưa đi làm, đã nghỉ hưu hoặc không có việc" error={errors.years_employed?.message}>
                <input type="number" step="0.5" min="0" max="50" placeholder="3"
                  className={`${FIELD_CLASS} ${errors.years_employed ? 'input-error' : ''}`}
                  {...register('years_employed', { required: 'Bắt buộc', min: { value: 0, message: 'Từ 0' }, max: { value: 50, message: 'Tối đa 50' } })} />
              </FieldRow>
              <FieldRow label="Tuổi" error={errors.age_years?.message}>
                <input type="number" step="1" min="18" max="100" placeholder="30"
                  className={`${FIELD_CLASS} ${errors.age_years ? 'input-error' : ''}`}
                  {...register('age_years', { required: 'Bắt buộc', min: { value: 18, message: 'Ít nhất 18 tuổi' }, max: { value: 100, message: 'Tối đa 100' } })} />
              </FieldRow>
            </div>

            <div className="grid sm:grid-cols-2 gap-5">
              <FieldRow label="Trình độ học vấn" error={errors.education_ordinal?.message}>
                <select className={`${SELECT_CLASS} ${errors.education_ordinal ? 'input-error' : ''}`} {...register('education_ordinal', { required: 'Bắt buộc' })}>
                  {EDUCATION_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </FieldRow>
              <FieldRow label="Tình trạng hôn nhân" error={errors.is_married_flag?.message}>
                <select className={`${SELECT_CLASS} ${errors.is_married_flag ? 'input-error' : ''}`} {...register('is_married_flag', { required: 'Bắt buộc' })}>
                  <option value="false">Chưa kết hôn</option>
                  <option value="true">Đã kết hôn</option>
                </select>
              </FieldRow>
            </div>

            {/* ── Section 3: Hồ sơ tín dụng (CIC) — Read-only ───────── */}
            <SectionTitle title="Hồ sơ tín dụng (CIC)" />

            {cicLoading ? (
              <div className="flex items-center gap-3 rounded-2xl bg-gray-50 p-4 ring-1 ring-gray-100">
                <LoadingSpinner size="sm" />
                <span className="text-sm text-gray-500">Đang tra cứu CIC...</span>
              </div>
            ) : cicData?.found ? (
              <div className="space-y-3">
                {/* CIC Source banner */}
                <div className="flex items-center gap-3 rounded-2xl border border-success-200 bg-success-50 p-4">
                  <svg className="w-4 h-4 text-success-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p className="text-xs text-success-700">
                    <strong>Dữ liệu được lấy tự động từ Trung tâm Thông tin Tín dụng (CIC)</strong> dựa trên CCCD của bạn. Thông tin này sẽ được sử dụng để đánh giá đơn vay.
                  </p>
                </div>

                {/* CIC data grid */}
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
                    <p className="text-sm font-semibold text-gray-800">{formatCurrency(cicData.record?.total_outstanding_debt || 0)}</p>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-[10px] uppercase tracking-wide text-gray-400 mb-1">Nghĩa vụ nợ hàng tháng</p>
                    <p className="text-sm font-semibold text-gray-800">${Number(cicData.record?.total_monthly_installment || 0).toLocaleString()}</p>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-[10px] uppercase tracking-wide text-gray-400 mb-1">Tiền quá hạn</p>
                    <p className={`text-sm font-semibold ${Number(cicData.record?.total_overdue_amount || 0) > 0 ? 'text-danger-600' : 'text-gray-800'}`}>
                      {formatCurrency(cicData.record?.total_overdue_amount || 0)}
                    </p>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-[10px] uppercase tracking-wide text-gray-400 mb-1">Ngày quá hạn cao nhất (12th)</p>
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
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-[10px] uppercase tracking-wide text-gray-400 mb-1">Danh sách đen</p>
                    <p className={`text-sm font-semibold ${cicData.record?.blacklist_flag ? 'text-danger-600' : 'text-success-600'}`}>
                      {cicData.record?.blacklist_flag ? 'Có' : 'Không'}
                    </p>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-[10px] uppercase tracking-wide text-gray-400 mb-1">Lần tra cứu tín dụng</p>
                    <p className="text-sm font-semibold text-gray-800">{cicData.record?.num_credit_inquiries ?? 0}</p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
                <div className="flex items-start gap-3">
                  <svg className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <div>
                    <p className="text-sm font-semibold text-amber-800 mb-1">Chưa có hồ sơ CIC</p>
                    <p className="text-xs text-amber-700">
                      Hệ thống không tìm thấy dữ liệu tín dụng liên kết với CCCD của bạn tại Trung tâm CIC. 
                      Bạn vẫn có thể nộp đơn — hệ thống sẽ đánh giá dựa trên các thông tin khác.
                      Tỷ lệ DTI sẽ được tính chỉ từ khoản vay mới (không có nợ cũ).
                    </p>
                  </div>
                </div>
              </div>
            )}

            <div className="pt-2">
              <button type="submit" disabled={loading} className="btn-primary w-full py-3.5 text-base shadow-lg shadow-primary-100">
                {loading && <LoadingSpinner size="sm" className="mr-2" />}
                {loading ? 'Đang phân tích hồ sơ...' : 'Nộp đơn & Phân tích AI'}
              </button>
            </div>
          </form>
        </div>
      </div>

      <RejectedRagAdvisorModal
        open={modal?.type === 'rejected'}
        evaluation={modal?.data}
        pendingAction={rejectedAdvisor.pendingAction}
        ragResponse={rejectedAdvisor.ragResponse}
        submitting={rejectedAdvisor.submitting}
        submittedMessage={rejectedAdvisor.submittedMessage}
        onClose={handleRejectedAdvisorClose}
        onCancel={handleRejectedAdvisorClose}
        onConfirm={handleRejectedAdvisorConfirm}
        onSubmitAnother={handleRejectedAdvisorSubmitAnother}
      />

      {/* ── Modal: SUCCESS ───────────────────────────────────── */}
      <Modal open={modal?.type === 'success'} onClose={() => setModal(null)} title="Kết quả đánh giá">
        <div className="text-center">
          <div className="w-16 h-16 bg-success-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-success-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h3 className="text-lg font-bold text-gray-900 mb-2">Đơn đã gửi thành công!</h3>
          <p className="text-gray-500 text-sm mb-5">
            Hồ sơ của bạn đang chờ admin xét duyệt. Chúng tôi sẽ thông báo sớm nhất có thể.
          </p>
          {modal?.data?.override_reason && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4 text-left">
              <div className="flex items-center gap-2 mb-1">
                <svg className="w-4 h-4 text-amber-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p className="text-xs font-semibold text-amber-800">Đánh giá bởi business rule</p>
                {modal?.data?.raw_default_probability != null && (
                  <span className="ml-auto text-[10px] font-medium text-amber-700 bg-amber-100 px-1.5 py-0.5 rounded">
                    ML thô: {(modal.data.raw_default_probability * 100).toFixed(1)}%
                  </span>
                )}
              </div>
              <p className="text-xs text-amber-700">{modal.data.override_reason}</p>
            </div>
          )}
          <div className="flex gap-3">
            <button onClick={() => navigate('/dashboard')} className="btn-outline flex-1">Về Dashboard</button>
            <button onClick={() => navigate(`/application/${modal?.data?.application_id}`)} className="btn-primary flex-1">
              Xem chi tiết
            </button>
          </div>
        </div>
      </Modal>



    </div>
  )
}

export default ApplyPage
