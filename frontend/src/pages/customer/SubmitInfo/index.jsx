import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { toast } from 'react-toastify'
import { getApplicationById, submitPersonalInfo } from '../../../services/applications'
import Modal from '../../../components/common/Modal'
import LoadingSpinner from '../../../components/common/LoadingSpinner'

const SubmitPersonalInfoPage = () => {
  const { id }     = useParams()
  const navigate   = useNavigate()
  const [appLoading, setAppLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [done,       setDone]       = useState(false)

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

  const onSubmit = async (data) => {
    setSubmitting(true)
    try {
      await submitPersonalInfo(id, {
        full_name:      data.full_name,
        id_card_number: data.id_card_number,
        phone:          data.phone,
        email:          data.email,
        date_of_birth:  data.date_of_birth,
        address:        data.address,
      })
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
          <h1 className="text-2xl font-bold text-gray-900">Nộp thông tin cá nhân</h1>
          <p className="text-gray-500 mt-1 text-sm">Thông tin được mã hoá và bảo mật theo tiêu chuẩn ngân hàng.</p>
        </div>

        {/* Approved notice */}
        <div className="bg-success-50 border border-success-200 rounded-xl p-4 mb-6">
          <p className="text-sm font-medium text-success-800">
            ✅ Đơn vay #{id} đã được admin phê duyệt! Vui lòng điền thông tin bên dưới để hoàn tất.
          </p>
        </div>

        <div className="card p-8">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
            <div>
              <label className="label">Họ và tên đầy đủ</label>
              <input type="text" placeholder="Nguyễn Văn A"
                className={`input ${errors.full_name ? 'input-error' : ''}`}
                {...register('full_name', { required: 'Bắt buộc' })} />
              {errors.full_name && <p className="error-msg">{errors.full_name.message}</p>}
            </div>

            <div className="grid sm:grid-cols-2 gap-5">
              <div>
                <label className="label">Số CCCD / CMND</label>
                <input type="text" placeholder="012345678901"
                  className={`input ${errors.id_card_number ? 'input-error' : ''}`}
                  {...register('id_card_number', {
                    required: 'Bắt buộc',
                    pattern: { value: /^\d{9,12}$/, message: 'CCCD phải có 9–12 chữ số' },
                  })} />
                {errors.id_card_number && <p className="error-msg">{errors.id_card_number.message}</p>}
              </div>

              <div>
                <label className="label">Số điện thoại</label>
                <input type="tel" placeholder="0912345678"
                  className={`input ${errors.phone ? 'input-error' : ''}`}
                  {...register('phone', {
                    required: 'Bắt buộc',
                    pattern: { value: /^[0-9+\-\s]{9,15}$/, message: 'Số điện thoại không hợp lệ' },
                  })} />
                {errors.phone && <p className="error-msg">{errors.phone.message}</p>}
              </div>
            </div>

            <div className="grid sm:grid-cols-2 gap-5">
              <div>
                <label className="label">Email</label>
                <input type="email" placeholder="you@example.com"
                  className={`input ${errors.email ? 'input-error' : ''}`}
                  {...register('email', {
                    required: 'Bắt buộc',
                    pattern: { value: /^\S+@\S+\.\S+$/, message: 'Email không hợp lệ' },
                  })} />
                {errors.email && <p className="error-msg">{errors.email.message}</p>}
              </div>

              <div>
                <label className="label">Ngày sinh</label>
                <input type="date"
                  className={`input ${errors.date_of_birth ? 'input-error' : ''}`}
                  max={new Date().toISOString().split('T')[0]}
                  {...register('date_of_birth', { required: 'Bắt buộc' })} />
                {errors.date_of_birth && <p className="error-msg">{errors.date_of_birth.message}</p>}
              </div>
            </div>

            <div>
              <label className="label">Địa chỉ thường trú</label>
              <textarea rows={3} placeholder="Số nhà, đường, phường/xã, quận/huyện, tỉnh/thành phố"
                className={`input resize-none ${errors.address ? 'input-error' : ''}`}
                {...register('address', { required: 'Bắt buộc', minLength: { value: 10, message: 'Địa chỉ quá ngắn' } })} />
              {errors.address && <p className="error-msg">{errors.address.message}</p>}
            </div>

            <button type="submit" disabled={submitting} className="btn-primary w-full py-3 text-base mt-2">
              {submitting && <LoadingSpinner size="sm" className="mr-2" />}
              {submitting ? 'Đang nộp...' : 'Nộp thông tin'}
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
            Thông tin cá nhân đã được ghi nhận. Chúng tôi sẽ xử lý và liên hệ với bạn qua email trong thời gian sớm nhất.
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
