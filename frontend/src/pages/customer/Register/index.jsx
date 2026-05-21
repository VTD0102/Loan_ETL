import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { toast } from 'react-toastify'
import { register as apiRegister } from '../../../services/auth'
import LoadingSpinner from '../../../components/common/LoadingSpinner'

const RegisterPage = () => {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)

  const { register, handleSubmit, watch, formState: { errors } } = useForm()
  const password = watch('password')

  const onSubmit = async (data) => {
    setLoading(true)
    try {
      await apiRegister({
        email: data.email,
        username: data.username,
        password: data.password,
        cccd: data.cccd,
        full_name: data.full_name,
        phone: data.phone,
        address: data.address,
      })
      toast.success('Đăng ký thành công! Vui lòng đăng nhập.')
      navigate('/login')
    } catch (err) {
      const msg = err.response?.data?.detail || 'Đăng ký thất bại. Vui lòng thử lại.'
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-white via-primary-50/40 to-white flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <Link to="/" className="inline-flex items-center gap-2 text-primary-600 font-bold text-xl">
            <span className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center text-white text-sm">CI</span>
            CreditIntel
          </Link>
          <h1 className="mt-4 text-2xl font-bold text-gray-900">Tạo tài khoản mới</h1>
          <p className="text-sm text-gray-500 mt-1">Đăng ký miễn phí, bắt đầu ngay</p>
        </div>

        <div className="card p-8">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
            {/* Full Name */}
            <div>
              <label className="label">Họ và tên</label>
              <input
                type="text"
                placeholder="Nguyễn Văn A"
                className={`input ${errors.full_name ? 'input-error' : ''}`}
                {...register('full_name', {
                  required: 'Họ tên là bắt buộc',
                  minLength: { value: 2, message: 'Tối thiểu 2 ký tự' },
                })}
              />
              {errors.full_name && <p className="error-msg">{errors.full_name.message}</p>}
            </div>

            {/* Email */}
            <div>
              <label className="label">Email</label>
              <input
                type="email"
                placeholder="you@example.com"
                className={`input ${errors.email ? 'input-error' : ''}`}
                {...register('email', {
                  required: 'Email là bắt buộc',
                  pattern: { value: /^\S+@\S+\.\S+$/, message: 'Email không hợp lệ' },
                })}
              />
              {errors.email && <p className="error-msg">{errors.email.message}</p>}
            </div>

            {/* Username */}
            <div>
              <label className="label">Tên đăng nhập</label>
              <input
                type="text"
                placeholder="Tên hiển thị"
                className={`input ${errors.username ? 'input-error' : ''}`}
                {...register('username', {
                  required: 'Tên đăng nhập là bắt buộc',
                  minLength: { value: 3, message: 'Tối thiểu 3 ký tự' },
                })}
              />
              {errors.username && <p className="error-msg">{errors.username.message}</p>}
            </div>

            {/* CCCD */}
            <div>
              <label className="label">Số CCCD</label>
              <input
                type="text"
                placeholder="Nhập 12 số CCCD"
                maxLength={12}
                className={`input ${errors.cccd ? 'input-error' : ''}`}
                {...register('cccd', {
                  required: 'CCCD là bắt buộc',
                  pattern: { value: /^[0-9]{12}$/, message: 'CCCD phải bao gồm đúng 12 chữ số' },
                })}
              />
              {errors.cccd && <p className="error-msg">{errors.cccd.message}</p>}
            </div>

            {/* Phone */}
            <div>
              <label className="label">Số điện thoại</label>
              <input
                type="tel"
                placeholder="0912 345 678"
                className={`input ${errors.phone ? 'input-error' : ''}`}
                {...register('phone', {
                  required: 'Số điện thoại là bắt buộc',
                  pattern: { value: /^[0-9+\-\s]{9,15}$/, message: 'Số điện thoại không hợp lệ' },
                })}
              />
              {errors.phone && <p className="error-msg">{errors.phone.message}</p>}
            </div>

            {/* Address */}
            <div>
              <label className="label">Địa chỉ</label>
              <input
                type="text"
                placeholder="123 Đường ABC, Quận XYZ, TP.HCM"
                className={`input ${errors.address ? 'input-error' : ''}`}
                {...register('address', {
                  required: 'Địa chỉ là bắt buộc',
                  minLength: { value: 5, message: 'Tối thiểu 5 ký tự' },
                })}
              />
              {errors.address && <p className="error-msg">{errors.address.message}</p>}
            </div>

            {/* Password */}
            <div>
              <label className="label">Mật khẩu</label>
              <input
                type="password"
                placeholder="Ít nhất 6 ký tự"
                className={`input ${errors.password ? 'input-error' : ''}`}
                {...register('password', {
                  required: 'Mật khẩu là bắt buộc',
                  minLength: { value: 6, message: 'Mật khẩu ít nhất 6 ký tự' },
                })}
              />
              {errors.password && <p className="error-msg">{errors.password.message}</p>}
            </div>

            {/* Confirm Password */}
            <div>
              <label className="label">Xác nhận mật khẩu</label>
              <input
                type="password"
                placeholder="Nhập lại mật khẩu"
                className={`input ${errors.confirmPassword ? 'input-error' : ''}`}
                {...register('confirmPassword', {
                  required: 'Vui lòng xác nhận mật khẩu',
                  validate: (v) => v === password || 'Mật khẩu không khớp',
                })}
              />
              {errors.confirmPassword && <p className="error-msg">{errors.confirmPassword.message}</p>}
            </div>

            <button type="submit" disabled={loading} className="btn-primary w-full py-3 text-base mt-2">
              {loading ? <LoadingSpinner size="sm" className="mr-2" /> : null}
              {loading ? 'Đang đăng ký...' : 'Đăng ký'}
            </button>
          </form>

          <p className="text-center text-sm text-gray-500 mt-6">
            Đã có tài khoản?{' '}
            <Link to="/login" className="text-primary-600 font-semibold hover:underline">
              Đăng nhập ngay
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}

export default RegisterPage
