import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { toast } from 'react-toastify'
import { evaluateApplication, confirmApplication } from '../../../services/applications'
import Modal from '../../../components/common/Modal'
import LoadingSpinner from '../../../components/common/LoadingSpinner'

// ── Constants ──────────────────────────────────────────────────────────────
const TERM_OPTIONS = [12, 36, 60]

const EMPLOYMENT_OPTIONS = [
  'Employed', 'Self-employed', 'Retired', 'Not employed', 'Other',
]

const LOAN_PURPOSE_OPTIONS = [
  { value: 'Education',  label: 'Giáo dục' },
  { value: 'Home',       label: 'Nhà ở / Bất động sản' },
  { value: 'Car',        label: 'Ô tô / Phương tiện' },
  { value: 'Business',   label: 'Kinh doanh' },
  { value: 'Medical',    label: 'Y tế / Sức khỏe' },
  { value: 'Personal',   label: 'Tiêu dùng cá nhân' },
  { value: 'Revolving',  label: 'Tín dụng tuần hoàn (Revolving)' },
]

const EDUCATION_OPTIONS = [
  { value: 1, label: 'Dưới THPT' },
  { value: 2, label: 'THPT' },
  { value: 3, label: 'Cao đẳng' },
  { value: 4, label: 'Đại học' },
  { value: 5, label: 'Sau đại học' },
]

const OCCUPATION_OPTIONS = [
  'Accountants', 'Cleaning staff', 'Cooking staff', 'Core staff', 'Drivers',
  'HR staff', 'High skill tech staff', 'IT staff', 'Laborers', 'Low-skill Laborers',
  'Managers', 'Medicine staff', 'Private service staff', 'Realty agents',
  'Sales staff', 'Secretaries', 'Security staff', 'Waiters/barmen staff',
  'Unknown / Không có nghề nghiệp cụ thể',
]

// ── Credit score band helper ───────────────────────────────────────────────
const scoreBand = (score) => {
  if (score >= 740) return { label: 'Xuất sắc', color: 'text-success-700', bg: 'bg-success-50' }
  if (score >= 670) return { label: 'Tốt', color: 'text-primary-700', bg: 'bg-primary-50' }
  if (score >= 580) return { label: 'Trung bình', color: 'text-warning-700', bg: 'bg-warning-50' }
  return { label: 'Yếu', color: 'text-danger-700', bg: 'bg-danger-50' }
}

// ── Helper components ──────────────────────────────────────────────────────
const FieldRow = ({ label, hint, error, children }) => (
  <div>
    <div className="flex items-center gap-1.5 mb-1.5">
      <label className="text-sm font-medium text-gray-700">{label}</label>
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
  <div className="flex items-center gap-3 pt-2">
    <span className="text-sm font-semibold text-gray-700">{title}</span>
    <div className="flex-1 h-px bg-gray-100" />
  </div>
)

// ── Chat Widget ────────────────────────────────────────────────────────────
const ChatWidget = ({ context, onClose }) => {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text: `Xin chào! Tôi là trợ lý AI của CreditIntel. Tôi đã được cung cấp thông tin về đơn vay của bạn${context ? ` (xác suất vỡ nợ: ${(context.default_probability * 100).toFixed(1)}%, rủi ro: ${context.risk_level})` : ''}. Bạn có thể hỏi tôi bất kỳ điều gì về hồ sơ vay.`,
    },
  ])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const messagesEndRef = useRef(null)

  const sendMessage = async () => {
    if (!input.trim() || sending) return
    const userMsg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', text: userMsg }])
    setSending(true)
    try {
      const { default: api } = await import('../../../services/api')
      const res = await api.post('/chat', {
        message: userMsg,
        session_id: null,
      })
      setMessages(prev => [...prev, { role: 'assistant', text: res.data.response }])
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', text: 'Xin lỗi, có lỗi khi kết nối AI. Vui lòng thử lại.' }])
    } finally {
      setSending(false)
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }

  return (
    <div className="fixed bottom-4 right-4 w-80 bg-white rounded-2xl shadow-2xl border border-gray-200 z-50 flex flex-col" style={{ height: '420px' }}>
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 bg-primary-600 rounded-t-2xl">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-green-400 rounded-full" />
          <span className="text-sm font-semibold text-white">Trợ lý AI CreditIntel</span>
        </div>
        <button onClick={onClose} className="text-white/70 hover:text-white">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] text-xs px-3 py-2 rounded-2xl ${
              m.role === 'user'
                ? 'bg-primary-600 text-white rounded-tr-sm'
                : 'bg-gray-100 text-gray-800 rounded-tl-sm'
            }`}>
              {m.text}
            </div>
          </div>
        ))}
        {sending && (
          <div className="flex justify-start">
            <div className="bg-gray-100 text-gray-500 text-xs px-3 py-2 rounded-2xl rounded-tl-sm">
              <LoadingSpinner size="sm" />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      <div className="flex gap-2 px-3 py-2 border-t border-gray-100">
        <input
          className="input flex-1 text-xs py-1.5"
          placeholder="Nhập câu hỏi..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && sendMessage()}
        />
        <button onClick={sendMessage} disabled={sending} className="btn-primary px-3 py-1.5 text-xs">
          Gửi
        </button>
      </div>
    </div>
  )
}

// ── Suggestion Modal (Pre-approval) ────────────────────────────────────────
const SuggestionModal = ({ open, evalResult, originalData, onConfirm, onClose }) => {
  const [confirmAmount, setConfirmAmount] = useState(originalData?.loan_amount || '')
  const [confirmTerm, setConfirmTerm] = useState(originalData?.term || 36)
  const [error, setError] = useState('')
  const [chatOpen, setChatOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  if (!open || !evalResult) return null

  const isLow    = evalResult.risk_level === 'Low'
  const prob     = (evalResult.default_probability * 100).toFixed(1)
  const maxAmt   = evalResult.suggested_amount
  const sugTerm  = evalResult.suggested_term
  const cs       = evalResult.credit_score_computed
  const csBand   = cs ? scoreBand(cs) : null

  const handleConfirm = async () => {
    const amt = parseFloat(confirmAmount)
    if (!amt || amt <= 0) { setError('Vui lòng nhập khoản vay hợp lệ'); return }
    if (amt > maxAmt) { setError(`Khoản vay không được vượt $${maxAmt.toLocaleString()}`); return }
    if (!TERM_OPTIONS.includes(Number(confirmTerm))) { setError('Kỳ hạn không hợp lệ'); return }
    setError('')
    setSubmitting(true)
    try {
      await onConfirm({ ...originalData, loan_amount: amt, term: Number(confirmTerm) })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <div className="fixed inset-0 bg-black/40 z-40 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg p-6">
          {/* Risk badge */}
          <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-semibold mb-4 ${
            isLow ? 'bg-success-50 text-success-700' : 'bg-warning-50 text-warning-700'
          }`}>
            <div className={`w-2 h-2 rounded-full ${isLow ? 'bg-success-500' : 'bg-warning-500'}`} />
            Rủi ro {isLow ? 'THẤP' : 'TRUNG BÌNH'}
          </div>

          <h2 className="text-lg font-bold text-gray-900 mb-1">
            {isLow ? 'Có khoản vay tối ưu hơn cho bạn' : 'Đơn vay trong mức chấp nhận được'}
          </h2>
          <p className="text-sm text-gray-500 mb-5">
            {isLow
              ? 'Với hồ sơ tài chính của bạn, hệ thống đề xuất khoản vay phù hợp hơn bên dưới.'
              : 'Khoản vay này có thể bị admin từ chối. Bạn nên xem xét điều chỉnh theo gợi ý.'}
          </p>

          {/* Info grid — includes computed credit score */}
          <div className="grid grid-cols-2 gap-3 bg-gray-50 rounded-xl p-4 mb-5 text-sm">
            <div>
              <p className="text-gray-500 text-xs mb-0.5">Xác suất vỡ nợ</p>
              <p className={`font-bold text-base ${isLow ? 'text-success-600' : 'text-warning-600'}`}>{prob}%</p>
            </div>
            {cs && csBand ? (
              <div>
                <p className="text-gray-500 text-xs mb-0.5">Điểm tín dụng tính toán</p>
                <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-semibold ${csBand.bg} ${csBand.color}`}>
                  {cs} — {csBand.label}
                </span>
              </div>
            ) : (
              <div>
                <p className="text-gray-500 text-xs mb-0.5">Khoản vay bạn chọn</p>
                <p className="font-semibold text-gray-800">${Number(originalData?.loan_amount).toLocaleString()} / {originalData?.term}th</p>
              </div>
            )}
            <div>
              <p className="text-gray-500 text-xs mb-0.5">Gợi ý tối đa an toàn</p>
              <p className="font-bold text-primary-600">${maxAmt.toLocaleString()}</p>
            </div>
            <div>
              <p className="text-gray-500 text-xs mb-0.5">Kỳ hạn phù hợp nhất</p>
              <p className="font-bold text-primary-600">{sugTerm} tháng</p>
            </div>
          </div>

          {/* Confirm inputs */}
          <p className="text-sm font-medium text-gray-700 mb-3">Xác nhận khoản vay cuối cùng:</p>
          <div className="grid grid-cols-2 gap-3 mb-2">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Số tiền vay (USD)</label>
              <input
                type="number"
                step="100"
                min="500"
                max={maxAmt}
                className="input"
                value={confirmAmount}
                onChange={e => { setConfirmAmount(e.target.value); setError('') }}
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Kỳ hạn</label>
              <select className="input" value={confirmTerm} onChange={e => { setConfirmTerm(Number(e.target.value)); setError('') }}>
                {TERM_OPTIONS.map(t => <option key={t} value={t}>{t} tháng</option>)}
              </select>
            </div>
          </div>
          {error && <p className="text-xs text-danger-600 mb-3">{error}</p>}
          <p className="text-xs text-gray-400 mb-5">
            Khoản vay không được vượt ${maxAmt.toLocaleString()} (giới hạn an toàn).
          </p>

          {/* Actions */}
          <div className="flex gap-3">
            <button
              onClick={() => setChatOpen(true)}
              className="btn-outline flex-1 flex items-center justify-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
              Chat với AI
            </button>
            <button
              onClick={handleConfirm}
              disabled={submitting}
              className="btn-primary flex-1 flex items-center justify-center gap-2"
            >
              {submitting && <LoadingSpinner size="sm" />}
              Xác nhận gửi đơn
            </button>
          </div>
        </div>
      </div>

      {chatOpen && <ChatWidget context={evalResult} onClose={() => setChatOpen(false)} />}
    </>
  )
}

// ── Main Apply page ────────────────────────────────────────────────────────
const ApplyPage = () => {
  const navigate  = useNavigate()
  const [loading, setLoading]         = useState(false)
  const [modal, setModal]             = useState(null)
  const [originalFormData, setOriginalFormData] = useState(null)
  const [chatOpen, setChatOpen]       = useState(false)

  const { register, handleSubmit, formState: { errors } } = useForm({
    defaultValues: {
      term: 36,
      employment_status: 'Employed',
      loan_purpose: 'Personal',
      occupation_type: 'Unknown / Không có nghề nghiệp cụ thể',
      years_employed: 0,
      is_homeowner: 'false',
      income_verifiable_flag: 'false',
      gender_male_flag: 'false',
      is_married_flag: 'false',
      education_ordinal: 4,
      cnt_children: 0,
      cnt_fam_members: 1,
      num_bureau_records: 0,
      num_active_credit: 0,
      total_overdue_amount: 0,
      max_credit_overdue_days: 0,
    },
  })

  const buildPayload = (data) => ({
    monthly_income:          parseFloat(data.monthly_income),
    loan_amount:             parseFloat(data.loan_amount),
    term:                    parseInt(data.term),
    employment_status:       data.employment_status,
    is_homeowner:            data.is_homeowner === 'true' || data.is_homeowner === true,
    loan_purpose:            data.loan_purpose,
    occupation_type:         data.occupation_type.includes('Unknown') ? 'Unknown' : data.occupation_type,
    years_employed:          parseFloat(data.years_employed) || 0,
    income_verifiable_flag:  data.income_verifiable_flag === 'true' || data.income_verifiable_flag === true,
    num_bureau_records:      parseInt(data.num_bureau_records) || 0,
    num_active_credit:       parseInt(data.num_active_credit) || 0,
    total_overdue_amount:    parseFloat(data.total_overdue_amount) || 0,
    max_credit_overdue_days: parseInt(data.max_credit_overdue_days) || 0,
    age_years:               parseInt(data.age_years),
    gender_male_flag:        data.gender_male_flag === 'true' || data.gender_male_flag === true,
    education_ordinal:       parseInt(data.education_ordinal),
    cnt_children:            parseInt(data.cnt_children) || 0,
    cnt_fam_members:         parseInt(data.cnt_fam_members) || 1,
    is_married_flag:         data.is_married_flag === 'true' || data.is_married_flag === true,
  })

  const onSubmit = async (data) => {
    setLoading(true)
    try {
      const payload = buildPayload(data)
      setOriginalFormData(payload)
      const res    = await evaluateApplication(payload)
      const result = res.data

      if (result.status === 'AUTO_REJECTED') {
        setModal({ type: 'rejected', data: result })
        return
      }

      if (result.is_perfect_fit) {
        const confirmRes = await confirmApplication(payload)
        setModal({ type: 'success', data: confirmRes.data })
      } else {
        setModal({ type: 'suggestion', data: result })
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Nộp đơn thất bại. Vui lòng thử lại.')
    } finally {
      setLoading(false)
    }
  }

  const handleConfirm = async (confirmedPayload) => {
    try {
      const res = await confirmApplication(confirmedPayload)
      setModal({ type: 'success', data: res.data })
    } catch (err) {
      const detail = err.response?.data?.detail
      if (err.response?.status === 422) {
        toast.error(detail || 'Khoản vay vượt mức an toàn được gợi ý.')
      } else {
        toast.error(detail || 'Gửi đơn thất bại. Vui lòng thử lại.')
      }
      throw err
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 py-10 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <button onClick={() => navigate('/dashboard')} className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-primary-600 mb-4 transition-colors">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Quay lại Dashboard
          </button>
          <h1 className="text-2xl font-bold text-gray-900">Nộp đơn vay mới</h1>
          <p className="text-gray-500 mt-1">Vui lòng điền đầy đủ thông tin. Hệ thống AI sẽ tính điểm tín dụng và đánh giá rủi ro tự động.</p>
        </div>

        <div className="card p-8">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>

            {/* ── Section 1: Thông tin khoản vay ──────────────────── */}
            <SectionTitle title="Thông tin khoản vay" />
            <div className="grid sm:grid-cols-2 gap-5">
              <FieldRow label="Thu nhập hàng tháng (USD)" error={errors.monthly_income?.message}>
                <input type="number" step="0.01" min="1" placeholder="5000"
                  className={`input ${errors.monthly_income ? 'input-error' : ''}`}
                  {...register('monthly_income', { required: 'Bắt buộc', min: { value: 1, message: 'Phải > 0' } })} />
              </FieldRow>
              <FieldRow label="Số tiền muốn vay (USD)" error={errors.loan_amount?.message}>
                <input type="number" step="0.01" min="500" placeholder="10000"
                  className={`input ${errors.loan_amount ? 'input-error' : ''}`}
                  {...register('loan_amount', { required: 'Bắt buộc', min: { value: 500, message: 'Tối thiểu $500' }, max: { value: 150000, message: 'Tối đa $150,000' } })} />
              </FieldRow>
            </div>

            <div className="grid sm:grid-cols-2 gap-5">
              <FieldRow label="Kỳ hạn vay" error={errors.term?.message}>
                <select className={`input ${errors.term ? 'input-error' : ''}`} {...register('term', { required: 'Bắt buộc' })}>
                  {TERM_OPTIONS.map(t => <option key={t} value={t}>{t} tháng</option>)}
                </select>
              </FieldRow>
              <FieldRow label="Mục đích vay" error={errors.loan_purpose?.message}>
                <select className={`input ${errors.loan_purpose ? 'input-error' : ''}`} {...register('loan_purpose', { required: 'Bắt buộc' })}>
                  {LOAN_PURPOSE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </FieldRow>
            </div>

            <div className="grid sm:grid-cols-1 gap-5">
              <FieldRow label="Có nhà riêng không?" error={errors.is_homeowner?.message}>
                <select className={`input ${errors.is_homeowner ? 'input-error' : ''}`} {...register('is_homeowner', { required: 'Bắt buộc' })}>
                  <option value="false">Không</option>
                  <option value="true">Có</option>
                </select>
              </FieldRow>
            </div>

            {/* ── Section 2: Thông tin cá nhân ─────────────────── */}
            <SectionTitle title="Thông tin cá nhân" />
            <div className="grid sm:grid-cols-2 gap-5">
              <FieldRow label="Tình trạng việc làm" error={errors.employment_status?.message}>
                <select className={`input ${errors.employment_status ? 'input-error' : ''}`} {...register('employment_status', { required: 'Bắt buộc' })}>
                  {EMPLOYMENT_OPTIONS.map(o => <option key={o} value={o}>{o}</option>)}
                </select>
              </FieldRow>
              <FieldRow label="Nghề nghiệp" error={errors.occupation_type?.message}>
                <select className={`input ${errors.occupation_type ? 'input-error' : ''}`} {...register('occupation_type', { required: 'Bắt buộc' })}>
                  {OCCUPATION_OPTIONS.map(o => <option key={o} value={o}>{o}</option>)}
                </select>
              </FieldRow>
            </div>

            <div className="grid sm:grid-cols-2 gap-5">
              <FieldRow label="Số năm kinh nghiệm làm việc" hint="0 nếu chưa đi làm, đã nghỉ hưu hoặc không có việc" error={errors.years_employed?.message}>
                <input type="number" step="0.5" min="0" max="50" placeholder="3"
                  className={`input ${errors.years_employed ? 'input-error' : ''}`}
                  {...register('years_employed', { required: 'Bắt buộc', min: { value: 0, message: 'Từ 0' }, max: { value: 50, message: 'Tối đa 50' } })} />
              </FieldRow>
              <FieldRow label="Thu nhập có thể xác minh?" hint="Có hợp đồng lao động, payslip hoặc tài liệu chứng minh thu nhập" error={errors.income_verifiable_flag?.message}>
                <select className={`input ${errors.income_verifiable_flag ? 'input-error' : ''}`} {...register('income_verifiable_flag', { required: 'Bắt buộc' })}>
                  <option value="true">Có (hợp đồng lao động, payslip...)</option>
                  <option value="false">Không</option>
                </select>
              </FieldRow>
            </div>

            <div className="grid sm:grid-cols-2 gap-5">
              <FieldRow label="Tuổi" error={errors.age_years?.message}>
                <input type="number" step="1" min="18" max="100" placeholder="30"
                  className={`input ${errors.age_years ? 'input-error' : ''}`}
                  {...register('age_years', { required: 'Bắt buộc', min: { value: 18, message: 'Ít nhất 18 tuổi' }, max: { value: 100, message: 'Tối đa 100' } })} />
              </FieldRow>
              <FieldRow label="Giới tính" error={errors.gender_male_flag?.message}>
                <select className={`input ${errors.gender_male_flag ? 'input-error' : ''}`} {...register('gender_male_flag', { required: 'Bắt buộc' })}>
                  <option value="false">Nữ</option>
                  <option value="true">Nam</option>
                </select>
              </FieldRow>
            </div>

            <div className="grid sm:grid-cols-2 gap-5">
              <FieldRow label="Trình độ học vấn" error={errors.education_ordinal?.message}>
                <select className={`input ${errors.education_ordinal ? 'input-error' : ''}`} {...register('education_ordinal', { required: 'Bắt buộc' })}>
                  {EDUCATION_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </FieldRow>
              <FieldRow label="Tình trạng hôn nhân" error={errors.is_married_flag?.message}>
                <select className={`input ${errors.is_married_flag ? 'input-error' : ''}`} {...register('is_married_flag', { required: 'Bắt buộc' })}>
                  <option value="false">Chưa kết hôn</option>
                  <option value="true">Đã kết hôn</option>
                </select>
              </FieldRow>
            </div>

            <div className="grid sm:grid-cols-2 gap-5">
              <FieldRow label="Số con" error={errors.cnt_children?.message}>
                <input type="number" step="1" min="0" max="20" placeholder="0"
                  className={`input ${errors.cnt_children ? 'input-error' : ''}`}
                  {...register('cnt_children', { required: 'Bắt buộc', min: { value: 0, message: 'Từ 0' } })} />
              </FieldRow>
              <FieldRow label="Số thành viên gia đình" error={errors.cnt_fam_members?.message}>
                <input type="number" step="1" min="1" max="20" placeholder="2"
                  className={`input ${errors.cnt_fam_members ? 'input-error' : ''}`}
                  {...register('cnt_fam_members', { required: 'Bắt buộc', min: { value: 1, message: 'Ít nhất 1' } })} />
              </FieldRow>
            </div>

            {/* ── Section 3: Lịch sử tín dụng ─────────────────── */}
            <SectionTitle title="Lịch sử tín dụng" />
            <div className="grid sm:grid-cols-2 gap-5">
              <FieldRow label="Số hồ sơ tín dụng" hint="Số lần bạn đã đăng ký tín dụng (vay, thẻ...)" error={errors.num_bureau_records?.message}>
                <input type="number" step="1" min="0" placeholder="2"
                  className={`input ${errors.num_bureau_records ? 'input-error' : ''}`}
                  {...register('num_bureau_records', { required: 'Bắt buộc', min: { value: 0, message: 'Từ 0' } })} />
              </FieldRow>
              <FieldRow label="Khoản tín dụng đang hoạt động" error={errors.num_active_credit?.message}>
                <input type="number" step="1" min="0" placeholder="1"
                  className={`input ${errors.num_active_credit ? 'input-error' : ''}`}
                  {...register('num_active_credit', { required: 'Bắt buộc', min: { value: 0, message: 'Từ 0' } })} />
              </FieldRow>
            </div>

            <div className="grid sm:grid-cols-2 gap-5">
              <FieldRow label="Tổng tiền quá hạn (USD)" error={errors.total_overdue_amount?.message}>
                <input type="number" step="0.01" min="0" placeholder="0"
                  className={`input ${errors.total_overdue_amount ? 'input-error' : ''}`}
                  {...register('total_overdue_amount', { required: 'Bắt buộc', min: { value: 0, message: 'Từ 0' } })} />
              </FieldRow>
              <FieldRow label="Số ngày quá hạn cao nhất" error={errors.max_credit_overdue_days?.message}>
                <input type="number" step="1" min="0" placeholder="0"
                  className={`input ${errors.max_credit_overdue_days ? 'input-error' : ''}`}
                  {...register('max_credit_overdue_days', { required: 'Bắt buộc', min: { value: 0, message: 'Từ 0' } })} />
              </FieldRow>
            </div>

            <div className="pt-2">
              <button type="submit" disabled={loading} className="btn-primary w-full py-3 text-base">
                {loading && <LoadingSpinner size="sm" className="mr-2" />}
                {loading ? 'Đang phân tích hồ sơ...' : 'Nộp đơn & Phân tích AI'}
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* ── Modal: AUTO_REJECTED ─────────────────────────────── */}
      <Modal open={modal?.type === 'rejected'} onClose={() => setModal(null)} title="Kết quả đánh giá">
        <div className="text-center">
          <div className="w-16 h-16 bg-danger-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-danger-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
          <h3 className="text-lg font-bold text-gray-900 mb-2">Đơn không đủ điều kiện</h3>
          {modal?.data?.credit_score_computed && (() => {
            const b = scoreBand(modal.data.credit_score_computed)
            return (
              <p className="text-sm text-gray-600 mb-2">
                Điểm tín dụng tính toán:{' '}
                <span className={`font-bold ${b.color}`}>
                  {modal.data.credit_score_computed} ({b.label})
                </span>
              </p>
            )
          })()}
          <p className="text-gray-500 text-sm mb-3">
            Xác suất vỡ nợ: <strong className="text-danger-600">{((modal?.data?.default_probability || 0) * 100).toFixed(1)}%</strong> — vượt ngưỡng 40%.
          </p>
          <div className="bg-danger-50 border border-danger-100 rounded-lg p-3 mb-4 text-left">
            <p className="text-sm font-medium text-danger-700 mb-1">Lý do từ chối:</p>
            <p className="text-xs text-danger-600">Mức rủi ro CAO — xác suất vỡ nợ vượt ngưỡng cho phép (40%)</p>
          </div>
          {modal?.data?.suggested_amount > 0 && (
            <div className="bg-primary-50 border border-primary-100 rounded-lg p-3 mb-4 text-left">
              <p className="text-sm font-medium text-primary-700 mb-1">Gợi ý khoản vay phù hợp:</p>
              <p className="text-xs text-primary-600">
                Tối đa <strong>${modal.data.suggested_amount.toLocaleString()}</strong> trong <strong>{modal.data.suggested_term} tháng</strong> có thể được chấp nhận.
              </p>
            </div>
          )}
          <div className="flex gap-3">
            <button
              onClick={() => setChatOpen(true)}
              className="btn-outline flex-1 flex items-center justify-center gap-2 text-sm"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
              Chat với AI
            </button>
            <button onClick={() => navigate('/dashboard')} className="btn-primary flex-1">
              Về Dashboard
            </button>
          </div>
        </div>
      </Modal>

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
          <div className="flex gap-3">
            <button onClick={() => navigate('/dashboard')} className="btn-outline flex-1">Về Dashboard</button>
            <button onClick={() => navigate(`/application/${modal?.data?.application_id}`)} className="btn-primary flex-1">
              Xem chi tiết
            </button>
          </div>
        </div>
      </Modal>

      {/* ── Pre-approval Suggestion Modal ─────────────────────── */}
      <SuggestionModal
        open={modal?.type === 'suggestion'}
        evalResult={modal?.data}
        originalData={originalFormData}
        onConfirm={handleConfirm}
        onClose={() => setModal(null)}
      />

      {/* ── Floating Chat Widget (after rejection) ─────────────── */}
      {chatOpen && (
        <ChatWidget
          context={modal?.data}
          onClose={() => setChatOpen(false)}
        />
      )}
    </div>
  )
}

export default ApplyPage
