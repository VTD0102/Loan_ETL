import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { toast } from 'react-toastify'
import { submitApplication } from '../../../services/applications'
import Modal from '../../../components/common/Modal'
import LoadingSpinner from '../../../components/common/LoadingSpinner'

const EMPLOYMENT_OPTIONS = ['Employed', 'Self-employed', 'Retired', 'Not employed', 'Other']
const TERM_OPTIONS       = [12, 36, 60]
const CATEGORY_OPTIONS   = [
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

const ApplyPage = () => {
  const navigate  = useNavigate()
  const [loading, setLoading]   = useState(false)
  const [modal, setModal]       = useState(null) // { type: 'rejected'|'success', app }
  const [optionalOpen, setOptionalOpen] = useState(false)

  const { register, handleSubmit, formState: { errors } } = useForm({
    defaultValues: { term: 36, employment_status: 'Employed', listing_category: 'Debt Consolidation' },
  })

  const onSubmit = async (data) => {
    setLoading(true)
    try {
      const payload = {
        monthly_income:    parseFloat(data.monthly_income),
        loan_amount:       parseFloat(data.loan_amount),
        term:              parseInt(data.term),
        employment_status: data.employment_status,
        dti:               parseFloat(data.dti),
        is_homeowner:      data.is_homeowner === 'true' || data.is_homeowner === true,
        listing_category:  data.listing_category,
        credit_score:      parseFloat(data.credit_score),
      }
      appendOptional(payload, data, 'ext_source_1', parseOptionalNumber)
      appendOptional(payload, data, 'ext_source_3', parseOptionalNumber)
      appendOptional(payload, data, 'num_bureau_records', parseOptionalInt)
      appendOptional(payload, data, 'num_active_credit', parseOptionalInt)
      appendOptional(payload, data, 'total_overdue_amount', parseOptionalNumber)
      appendOptional(payload, data, 'max_credit_overdue_days', parseOptionalInt)
      appendOptional(payload, data, 'has_bad_debt', parseOptionalBool)
      appendOptional(payload, data, 'income_verifiable_flag', parseOptionalBool)
      appendOptional(payload, data, 'age_years', parseOptionalInt)
      appendOptional(payload, data, 'gender_male_flag', parseOptionalBool)
      appendOptional(payload, data, 'education_ordinal', parseOptionalInt)
      appendOptional(payload, data, 'cnt_children', parseOptionalInt)
      appendOptional(payload, data, 'cnt_fam_members', parseOptionalInt)
      appendOptional(payload, data, 'is_married_flag', parseOptionalBool)
      const res = await submitApplication(payload)
      setModal({ type: res.data.status === 'AUTO_REJECTED' ? 'rejected' : 'success', app: res.data })

    } catch (err) {
      toast.error(err.response?.data?.detail || 'Nộp đơn thất bại. Vui lòng thử lại.')
    } finally {
      setLoading(false)
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
          <p className="text-gray-500 mt-1">Điền thông tin bên dưới. AI sẽ đánh giá hồ sơ trong vài giây.</p>
        </div>

        <div className="card p-8">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
            {/* Section: Financial */}
            <SectionTitle title="Thông tin tài chính" />

            <div className="grid sm:grid-cols-2 gap-5">
              <FieldRow label="Thu nhập hàng tháng (USD)" error={errors.monthly_income?.message}>
                <input type="number" step="0.01" min="0" placeholder="Ví dụ: 5000"
                  className={`input ${errors.monthly_income ? 'input-error' : ''}`}
                  {...register('monthly_income', {
                    required: 'Bắt buộc',
                    min: { value: 1, message: 'Phải lớn hơn 0' },
                  })}
                />
              </FieldRow>

              <FieldRow label="Số tiền muốn vay (USD)" error={errors.loan_amount?.message}>
                <input type="number" step="0.01" min="0" placeholder="Ví dụ: 10000"
                  className={`input ${errors.loan_amount ? 'input-error' : ''}`}
                  {...register('loan_amount', {
                    required: 'Bắt buộc',
                    min: { value: 1,     message: 'Phải lớn hơn 0'     },
                    max: { value: 40000, message: 'Tối đa $40,000'      },
                  })}
                />
              </FieldRow>
            </div>

            <div className="grid sm:grid-cols-2 gap-5">
              <FieldRow label="Kỳ hạn vay" error={errors.term?.message}>
                <select className={`input ${errors.term ? 'input-error' : ''}`}
                  {...register('term', { required: 'Bắt buộc' })}>
                  {TERM_OPTIONS.map((t) => (
                    <option key={t} value={t}>{t} tháng</option>
                  ))}
                </select>
              </FieldRow>

              <FieldRow
                label="Tỷ lệ nợ/Thu nhập (DTI %)"
                hint="Debt-to-Income Ratio: tổng nghĩa vụ nợ hàng tháng ÷ thu nhập hàng tháng × 100"
                error={errors.dti?.message}
              >
                <input type="number" step="0.01" min="0" max="100" placeholder="Ví dụ: 20"
                  className={`input ${errors.dti ? 'input-error' : ''}`}
                  {...register('dti', {
                    required: 'Bắt buộc',
                    min: { value: 0,   message: 'Từ 0%'   },
                    max: { value: 100, message: 'Tối đa 100%' },
                  })}
                />
              </FieldRow>
            </div>

            {/* Section: Personal */}
            <SectionTitle title="Thông tin cá nhân" />

            <div className="grid sm:grid-cols-2 gap-5">
              <FieldRow label="Tình trạng việc làm" error={errors.employment_status?.message}>
                <select className={`input ${errors.employment_status ? 'input-error' : ''}`}
                  {...register('employment_status', { required: 'Bắt buộc' })}>
                  {EMPLOYMENT_OPTIONS.map((o) => (
                    <option key={o} value={o}>{o}</option>
                  ))}
                </select>
              </FieldRow>

              <FieldRow label="Điểm tín dụng (300–850)" error={errors.credit_score?.message}>
                <input type="number" step="1" min="300" max="850" placeholder="Ví dụ: 680"
                  className={`input ${errors.credit_score ? 'input-error' : ''}`}
                  {...register('credit_score', {
                    required: 'Bắt buộc',
                    min: { value: 300, message: 'Tối thiểu 300' },
                    max: { value: 850, message: 'Tối đa 850'    },
                  })}
                />
              </FieldRow>
            </div>

            <div className="grid sm:grid-cols-2 gap-5">
              <FieldRow label="Mục đích vay" error={errors.listing_category?.message}>
                <select className={`input ${errors.listing_category ? 'input-error' : ''}`}
                  {...register('listing_category', { required: 'Bắt buộc' })}>
                  {CATEGORY_OPTIONS.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </FieldRow>

              <FieldRow label="Có nhà riêng không?" error={errors.is_homeowner?.message}>
                <select className={`input ${errors.is_homeowner ? 'input-error' : ''}`}
                  {...register('is_homeowner', { required: 'Bắt buộc' })}>
                  <option value="false">Không</option>
                  <option value="true">Có</option>
                </select>
              </FieldRow>
            </div>

            <div className="border border-gray-200 rounded-lg">
              <button
                type="button"
                onClick={() => setOptionalOpen((v) => !v)}
                className="w-full flex items-center justify-between px-4 py-3 text-left"
              >
                <span className="text-sm font-semibold text-gray-700">Thông tin bổ sung cho mô hình</span>
                <svg className={`w-4 h-4 text-gray-500 transition-transform ${optionalOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {optionalOpen && (
                <div className="px-4 pb-4 border-t border-gray-100 space-y-5">
                  <div className="grid sm:grid-cols-2 gap-5 pt-4">
                    <FieldRow label="EXT source 1">
                      <input type="number" step="0.0001" min="0" max="1" placeholder="0.42" className="input" {...register('ext_source_1')} />
                    </FieldRow>
                    <FieldRow label="EXT source 3">
                      <input type="number" step="0.0001" min="0" max="1" placeholder="0.51" className="input" {...register('ext_source_3')} />
                    </FieldRow>
                  </div>

                  <div className="grid sm:grid-cols-2 gap-5">
                    <FieldRow label="Số hồ sơ tín dụng">
                      <input type="number" step="1" min="0" className="input" {...register('num_bureau_records')} />
                    </FieldRow>
                    <FieldRow label="Khoản tín dụng đang hoạt động">
                      <input type="number" step="1" min="0" className="input" {...register('num_active_credit')} />
                    </FieldRow>
                  </div>

                  <div className="grid sm:grid-cols-2 gap-5">
                    <FieldRow label="Tổng tiền quá hạn (USD)">
                      <input type="number" step="0.01" min="0" className="input" {...register('total_overdue_amount')} />
                    </FieldRow>
                    <FieldRow label="Số ngày quá hạn cao nhất">
                      <input type="number" step="1" min="0" className="input" {...register('max_credit_overdue_days')} />
                    </FieldRow>
                  </div>

                  <div className="grid sm:grid-cols-2 gap-5">
                    <FieldRow label="Có nợ xấu?">
                      <select className="input" defaultValue="" {...register('has_bad_debt')}>
                        <option value="">Không cung cấp</option>
                        <option value="false">Không</option>
                        <option value="true">Có</option>
                      </select>
                    </FieldRow>
                    <FieldRow label="Thu nhập xác minh được?">
                      <select className="input" defaultValue="" {...register('income_verifiable_flag')}>
                        <option value="">Không cung cấp</option>
                        <option value="false">Không</option>
                        <option value="true">Có</option>
                      </select>
                    </FieldRow>
                  </div>

                  <div className="grid sm:grid-cols-2 gap-5">
                    <FieldRow label="Tuổi">
                      <input type="number" step="1" min="18" max="100" className="input" {...register('age_years')} />
                    </FieldRow>
                    <FieldRow label="Giới tính nam?">
                      <select className="input" defaultValue="" {...register('gender_male_flag')}>
                        <option value="">Không cung cấp</option>
                        <option value="false">Không</option>
                        <option value="true">Có</option>
                      </select>
                    </FieldRow>
                  </div>

                  <div className="grid sm:grid-cols-2 gap-5">
                    <FieldRow label="Trình độ học vấn">
                      <select className="input" defaultValue="" {...register('education_ordinal')}>
                        <option value="">Không cung cấp</option>
                        {EDUCATION_OPTIONS.map((o) => (
                          <option key={o.value} value={o.value}>{o.label}</option>
                        ))}
                      </select>
                    </FieldRow>
                    <FieldRow label="Đã kết hôn?">
                      <select className="input" defaultValue="" {...register('is_married_flag')}>
                        <option value="">Không cung cấp</option>
                        <option value="false">Không</option>
                        <option value="true">Có</option>
                      </select>
                    </FieldRow>
                  </div>

                  <div className="grid sm:grid-cols-2 gap-5">
                    <FieldRow label="Số con">
                      <input type="number" step="1" min="0" className="input" {...register('cnt_children')} />
                    </FieldRow>
                    <FieldRow label="Số thành viên gia đình">
                      <input type="number" step="1" min="1" className="input" {...register('cnt_fam_members')} />
                    </FieldRow>
                  </div>
                </div>
              )}
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

      {/* Modal: AUTO_REJECTED */}
      <Modal
        open={modal?.type === 'rejected'}
        onClose={() => setModal(null)}
        title="Kết quả đánh giá"
      >
        <div className="text-center">
          <div className="w-16 h-16 bg-danger-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-danger-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
          <h3 className="text-lg font-bold text-gray-900 mb-2">Đơn không đủ điều kiện</h3>
          <p className="text-gray-500 text-sm mb-3">
            Hệ thống AI đánh giá hồ sơ của bạn có xác suất vỡ nợ cao ({((modal?.app?.default_probability || 0) * 100).toFixed(1)}%) — vượt ngưỡng cho phép.
          </p>
          <div className="bg-danger-50 border border-danger-100 rounded-lg p-3 mb-5 text-left">
            <p className="text-sm font-medium text-danger-700 mb-1">Lý do từ chối:</p>
            <p className="text-xs text-danger-600">Mức độ rủi ro: <strong>CAO</strong> — Điểm rủi ro vượt ngưỡng 40%</p>
          </div>
          <p className="text-xs text-gray-400 mb-4">Bạn có thể cải thiện hồ sơ và nộp đơn mới sau.</p>
          <button onClick={() => navigate('/dashboard')} className="btn-primary w-full">
            Về Dashboard
          </button>
        </div>
      </Modal>

      {/* Modal: SUCCESS (PENDING_REVIEW) */}
      <Modal
        open={modal?.type === 'success'}
        onClose={() => setModal(null)}
        title="Kết quả đánh giá"
      >
        <div className="text-center">
          <div className="w-16 h-16 bg-success-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-success-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h3 className="text-lg font-bold text-gray-900 mb-2">Đơn đã nộp thành công!</h3>
          <p className="text-gray-500 text-sm mb-5">
            Hồ sơ của bạn đang chờ admin xét duyệt. Chúng tôi sẽ thông báo sớm nhất có thể.
          </p>
          <div className="flex gap-3">
            <button onClick={() => navigate('/dashboard')} className="btn-outline flex-1">Về Dashboard</button>
            <button onClick={() => navigate(`/application/${modal?.app?.application_id}`)} className="btn-primary flex-1">
              Xem chi tiết
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

const SectionTitle = ({ title }) => (
  <div className="flex items-center gap-3 pt-2">
    <span className="text-sm font-semibold text-gray-700">{title}</span>
    <div className="flex-1 h-px bg-gray-100" />
  </div>
)

const appendOptional = (payload, data, key, parser) => {
  if (data[key] === undefined || data[key] === null || data[key] === '') return
  payload[key] = parser(data[key])
}

const parseOptionalNumber = (value) => parseFloat(value)
const parseOptionalInt = (value) => parseInt(value, 10)
const parseOptionalBool = (value) => value === true || value === 'true'

export default ApplyPage
