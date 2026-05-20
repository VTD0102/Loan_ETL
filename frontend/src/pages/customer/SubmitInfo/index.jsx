import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { toast } from 'react-toastify'
import { getApplicationById, submitPersonalInfo, uploadDocuments } from '../../../services/applications'
import Modal from '../../../components/common/Modal'
import LoadingSpinner from '../../../components/common/LoadingSpinner'
import useAuthStore from '../../../store/authStore'

const ACCEPTED = '.pdf,.doc,.docx,.jpg,.jpeg,.png'
const MAX_MB   = 10

const BANK_OPTIONS = [
  'Vietcombank',
  'BIDV',
  'VietinBank',
  'Techcombank',
  'MB Bank',
  'ACB',
  'Sacombank',
  'VPBank',
  'TPBank',
  'Agribank',
  'Khác',
]

const BRANCH_OPTIONS = [
  'Chi nhánh Trung tâm - TP.HCM',
  'Chi nhánh Hoàng Kiếm - Hà Nội',
  'Chi nhánh Hải Châu - Đà Nẵng',
  'Chi nhánh Ninh Kiều - Cần Thơ',
  'Chi nhánh Thủ Đức - TP.HCM',
]

const SubmitPersonalInfoPage = () => {
  const { id }   = useParams()
  const navigate = useNavigate()
  const user     = useAuthStore(s => s.user)

  const [appLoading, setAppLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [done,       setDone]       = useState(false)
  const [files,      setFiles]      = useState([])
  const [disbursementMethod, setDisbursementMethod] = useState('bank') // 'bank' | 'cash'
  const fileInputRef = useRef(null)

  const { register, handleSubmit, formState: { errors } } = useForm()

  useEffect(() => {
    const check = async () => {
      try {
        const res = await getApplicationById(id)
        if (res.data.status !== 'AWAITING_INFO') {
          toast.info('Đơn vay không ở trạng thái chờ thông tin.')
          navigate(`/application/${id}`, { replace: true })
        }
      } catch {
        navigate('/dashboard', { replace: true })
      } finally {
        setAppLoading(false)
      }
    }
    check()
  }, [id, navigate])

  /* ── File handling ── */
  const handleFileChange = (e) => {
    const selected = Array.from(e.target.files || [])
    const oversize = selected.filter(f => f.size > MAX_MB * 1024 * 1024)
    if (oversize.length) {
      toast.error(`File "${oversize[0].name}" vượt quá ${MAX_MB} MB`)
      return
    }
    setFiles(prev => {
      const names = new Set(prev.map(f => f.name))
      return [...prev, ...selected.filter(f => !names.has(f.name))]
    })
    e.target.value = ''
  }

  const removeFile = (name) => setFiles(prev => prev.filter(f => f.name !== name))

  /* ── Submit ── */
  const onSubmit = async (data) => {
    setSubmitting(true)
    try {
      const bankInfo = disbursementMethod === 'bank'
        ? `${data.bank_name} - ${data.bank_account_number}`
        : `Tiền mặt - ${data.branch}`

      // Backend still needs full personal_info — auto-fill from user registration
      await submitPersonalInfo(id, {
        full_name:           user?.full_name || user?.username || 'N/A',
        id_card_number:      user?.cccd || '000000000000',
        phone:               user?.phone || '0000000000',
        email:               user?.email || 'n/a@example.com',
        date_of_birth:       '1990-01-01',  // Placeholder — already on record
        address:             user?.address || 'N/A',
        bank_account_number: bankInfo,
      })

      // Upload documents if any
      if (files.length > 0) {
        const form = new FormData()
        form.append('bank_account_number', bankInfo)
        files.forEach(f => form.append('files', f))
        await uploadDocuments(id, form)
      }

      setDone(true)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Nộp thông tin thất bại. Vui lòng thử lại.')
    } finally {
      setSubmitting(false)
    }
  }

  if (appLoading) return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <LoadingSpinner size="lg" />
    </div>
  )

  return (
    <div className="min-h-screen bg-gray-50 py-10 px-4">
      <div className="max-w-lg mx-auto">
        <button onClick={() => navigate(`/application/${id}`)}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-primary-600 mb-6 transition-colors">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Quay lại đơn vay
        </button>

        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Thông tin nhận giải ngân</h1>
          <p className="text-gray-500 mt-1 text-sm">Đơn vay đã được duyệt! Vui lòng chọn phương thức nhận tiền.</p>
        </div>

        {/* Auto-filled Personal Info Preview */}
        <div className="card p-5 mb-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Thông tin cá nhân (đã đăng ký)</h3>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-0.5">Họ tên</p>
              <p className="font-medium text-gray-800">{user?.full_name || user?.username || '—'}</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-0.5">CCCD</p>
              <p className="font-medium text-gray-800">{user?.cccd || '—'}</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-0.5">Điện thoại</p>
              <p className="font-medium text-gray-800">{user?.phone || '—'}</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-0.5">Email</p>
              <p className="font-medium text-gray-800">{user?.email || '—'}</p>
            </div>
          </div>
        </div>

        <div className="card p-8">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>

            {/* Phương thức nhận tiền */}
            <div>
              <label className="label mb-3">Phương thức nhận tiền</label>
              <div className="grid grid-cols-2 gap-3">
                <button type="button"
                  onClick={() => setDisbursementMethod('bank')}
                  className={`p-4 rounded-xl border-2 text-left transition-all ${
                    disbursementMethod === 'bank'
                      ? 'border-primary-500 bg-primary-50 ring-2 ring-primary-200'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <p className="font-semibold text-gray-900 text-sm">🏦 Chuyển khoản</p>
                  <p className="text-xs text-gray-500 mt-1">Nhận tiền qua tài khoản ngân hàng</p>
                </button>
                <button type="button"
                  onClick={() => setDisbursementMethod('cash')}
                  className={`p-4 rounded-xl border-2 text-left transition-all ${
                    disbursementMethod === 'cash'
                      ? 'border-primary-500 bg-primary-50 ring-2 ring-primary-200'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <p className="font-semibold text-gray-900 text-sm">💵 Tiền mặt</p>
                  <p className="text-xs text-gray-500 mt-1">Nhận tại chi nhánh CreditIntel</p>
                </button>
              </div>
            </div>

            {/* Bank fields */}
            {disbursementMethod === 'bank' && (
              <>
                <div>
                  <label className="label">Ngân hàng</label>
                  <select
                    className={`input ${errors.bank_name ? 'input-error' : ''}`}
                    {...register('bank_name', { required: disbursementMethod === 'bank' ? 'Bắt buộc' : false })}
                  >
                    <option value="">Chọn ngân hàng</option>
                    {BANK_OPTIONS.map(b => <option key={b} value={b}>{b}</option>)}
                  </select>
                  {errors.bank_name && <p className="error-msg">{errors.bank_name.message}</p>}
                </div>

                <div>
                  <label className="label">Số tài khoản</label>
                  <input type="text" placeholder="Nhập số tài khoản nhận giải ngân"
                    className={`input ${errors.bank_account_number ? 'input-error' : ''}`}
                    {...register('bank_account_number', {
                      required: disbursementMethod === 'bank' ? 'Bắt buộc' : false,
                      pattern: { value: /^\d{6,20}$/, message: 'Số tài khoản phải có 6–20 chữ số' },
                    })} />
                  {errors.bank_account_number && <p className="error-msg">{errors.bank_account_number.message}</p>}
                </div>
              </>
            )}

            {/* Cash fields */}
            {disbursementMethod === 'cash' && (
              <div>
                <label className="label">Chọn chi nhánh nhận tiền</label>
                <select
                  className={`input ${errors.branch ? 'input-error' : ''}`}
                  {...register('branch', { required: disbursementMethod === 'cash' ? 'Bắt buộc' : false })}
                >
                  <option value="">Chọn chi nhánh</option>
                  {BRANCH_OPTIONS.map(b => <option key={b} value={b}>{b}</option>)}
                </select>
                {errors.branch && <p className="error-msg">{errors.branch.message}</p>}
              </div>
            )}

            {/* Tải lên tài liệu */}
            <div>
              <label className="label">
                Tài liệu minh chứng
                <span className="text-gray-400 font-normal ml-1">(tuỳ chọn)</span>
              </label>
              <p className="text-xs text-gray-400 mb-2">
                PDF, DOC, DOCX, JPG, PNG — tối đa {MAX_MB} MB mỗi file.
              </p>

              <button type="button"
                onClick={() => fileInputRef.current?.click()}
                className="w-full border-2 border-dashed border-gray-300 rounded-lg p-4 text-sm text-gray-500
                           hover:border-primary-400 hover:text-primary-600 transition-colors text-center">
                <svg className="w-5 h-5 mx-auto mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                </svg>
                Chọn file hoặc kéo thả vào đây
              </button>
              <input ref={fileInputRef} type="file" multiple accept={ACCEPTED}
                className="hidden" onChange={handleFileChange} />

              {files.length > 0 && (
                <ul className="mt-3 space-y-2">
                  {files.map(f => (
                    <li key={f.name}
                      className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2 text-sm">
                      <span className="truncate text-gray-700 max-w-[80%]">{f.name}</span>
                      <button type="button" onClick={() => removeFile(f.name)}
                        className="text-gray-400 hover:text-danger-500 ml-2 flex-shrink-0">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <button type="submit" disabled={submitting} className="btn-primary w-full py-3 text-base mt-2">
              {submitting && <LoadingSpinner size="sm" className="mr-2" />}
              {submitting ? 'Đang nộp...' : 'Xác nhận thông tin nhận tiền'}
            </button>
          </form>
        </div>
      </div>

      {/* Success Modal */}
      <Modal open={done} onClose={() => navigate(`/application/${id}`)} title="Nộp thành công!">
        <div className="text-center">
          <div className="w-16 h-16 bg-success-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-success-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <p className="text-gray-600 text-sm mb-6">
            Thông tin nhận tiền đã được ghi nhận. Hệ thống sẽ xử lý giải ngân và thông báo qua email khi hoàn tất.
          </p>
          <button onClick={() => navigate(`/application/${id}`)} className="btn-primary w-full">
            Xem chi tiết đơn vay
          </button>
        </div>
      </Modal>
    </div>
  )
}

export default SubmitPersonalInfoPage
