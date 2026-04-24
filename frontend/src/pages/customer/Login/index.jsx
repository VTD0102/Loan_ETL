import { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { toast } from 'react-toastify'
import { login as apiLogin } from '../../../services/auth'
import useAuthStore from '../../../store/authStore'
import LoadingSpinner from '../../../components/common/LoadingSpinner'

const LoginPage = () => {
  const navigate = useNavigate()
  const location  = useLocation()
  const setAuth   = useAuthStore((s) => s.setAuth)
  const [loading, setLoading] = useState(false)

  const { register, handleSubmit, formState: { errors } } = useForm()

  const from = location.state?.from?.pathname || '/dashboard'

  const onSubmit = async (data) => {
    setLoading(true)
    try {
      const res = await apiLogin({ email: data.email, password: data.password })
      setAuth(res.data.access_token, res.data.user)
      toast.success(`Chào mừng, ${res.data.user.username}!`)
      navigate(from, { replace: true })
    } catch (err) {
      const msg = err.response?.data?.detail || 'Sai email hoặc mật khẩu.'
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
          <h1 className="mt-4 text-2xl font-bold text-gray-900">Đăng nhập</h1>
          <p className="text-sm text-gray-500 mt-1">Chào mừng trở lại!</p>
        </div>

        <div className="card p-8">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
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

            <div>
              <label className="label">Mật khẩu</label>
              <input
                type="password"
                placeholder="••••••••"
                className={`input ${errors.password ? 'input-error' : ''}`}
                {...register('password', { required: 'Mật khẩu là bắt buộc' })}
              />
              {errors.password && <p className="error-msg">{errors.password.message}</p>}
            </div>

            <button type="submit" disabled={loading} className="btn-primary w-full py-3 text-base mt-2">
              {loading && <LoadingSpinner size="sm" className="mr-2" />}
              {loading ? 'Đang đăng nhập...' : 'Đăng nhập'}
            </button>
          </form>

          <p className="text-center text-sm text-gray-500 mt-6">
            Chưa có tài khoản?{' '}
            <Link to="/register" className="text-primary-600 font-semibold hover:underline">
              Đăng ký ngay
            </Link>
          </p>

          <div className="mt-8 border-t border-gray-100 pt-6 text-center">
            <Link to="/admin/login" className="text-xs text-gray-400 hover:text-primary-600 transition-colors">
              👉 Nhân viên quản lý? Đăng nhập Admin
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}

export default LoginPage
