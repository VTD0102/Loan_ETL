import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { toast } from 'react-toastify'
import { login as apiLogin } from '../../../services/auth'
import useAuthStore from '../../../store/authStore'
import LoadingSpinner from '../../../components/common/LoadingSpinner'

const AdminLoginPage = () => {
  const navigate  = useNavigate()
  const setAuth   = useAuthStore((s) => s.setAuth)
  const [loading, setLoading] = useState(false)

  const { register, handleSubmit, formState: { errors } } = useForm()

  const onSubmit = async (data) => {
    setLoading(true)
    try {
      const res = await apiLogin({ email: data.email, password: data.password })
      const { access_token, user } = res.data

      // Kiểm tra role
      if (user?.role !== 'admin') {
        toast.error('Tài khoản không có quyền admin.')
        return
      }

      setAuth(access_token, user)
      toast.success(`Chào mừng trở lại, ${user.username}!`)
      navigate('/admin/dashboard', { replace: true })
    } catch (err) {
      const msg = err.response?.data?.detail || 'Sai email hoặc mật khẩu.'
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-white via-primary-50/40 to-white flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md animate-fade-in">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-3 mb-4">
            <span className="w-10 h-10 bg-primary-600 rounded-xl flex items-center justify-center text-white font-bold text-base">
              CI
            </span>
            <div className="text-left">
              <p className="text-gray-900 font-bold text-lg leading-tight">CreditIntel</p>
              <p className="text-gray-500 text-sm leading-tight">Admin Portal</p>
            </div>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Đăng nhập quản trị</h1>
          <p className="text-gray-500 text-sm mt-1">Chỉ dành cho nhân viên có thẩm quyền</p>
        </div>

        <div className="card p-8">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
            <div>
              <label className="label">Email</label>
              <input
                type="email"
                placeholder="admin@creditintel.dev"
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

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-3 text-base mt-2 flex items-center justify-center gap-2"
            >
              {loading && <LoadingSpinner size="sm" />}
              {loading ? 'Đang đăng nhập...' : 'Đăng nhập'}
            </button>
          </form>

          <div className="mt-6 pt-5 border-t border-gray-100 text-center">
            <Link to="/login" className="text-sm text-gray-500 hover:text-primary-600 transition-colors">
              ← Về trang đăng nhập khách hàng
            </Link>
          </div>
        </div>

        {/* Mock hint */}
        <p className="text-center text-xs text-gray-400 mt-6">
          Mock mode: dùng email có chứa "admin" để đăng nhập với quyền admin
        </p>
      </div>
    </div>
  )
}

export default AdminLoginPage
