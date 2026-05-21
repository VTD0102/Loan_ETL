import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-toastify'
import useAuthStore from '../../../store/authStore'
import { getProfile, updateProfile } from '../../../services/auth'
import LoadingSpinner from '../../../components/common/LoadingSpinner'
import { formatDate } from '../../../utils/format'

const AdminProfilePage = () => {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const setUser = useAuthStore((s) => s.setUser)

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState({})

  // Form states
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [address, setAddress] = useState('')
  const [password, setPassword] = useState('')

  // Read-only states (from backend User model)
  const [fullName, setFullName] = useState('')
  const [phone, setPhone] = useState('')
  const [cccd, setCccd] = useState('')
  const [createdAt, setCreatedAt] = useState('')

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const res = await getProfile()
        const data = res.data
        
        setUsername(data.username || '')
        setEmail(data.email || '')
        setAddress(data.address || '')
        
        // Read-only fields
        setFullName(data.full_name || 'Quản trị viên')
        setPhone(data.phone || 'Chưa cung cấp')
        setCccd(data.cccd || 'Chưa cung cấp')
        setCreatedAt(data.created_at || '')
      } catch (err) {
        toast.error('Không thể tải thông tin hồ sơ. Đang dùng thông tin từ bộ nhớ tạm.')
        // Fallback to auth store user data
        if (user) {
          setUsername(user.username || '')
          setEmail(user.email || '')
          setAddress(user.address || '')
          setFullName(user.full_name || 'Quản trị viên')
          setPhone(user.phone || 'Chưa cung cấp')
          setCccd(user.cccd || 'Chưa cung cấp')
          setCreatedAt(user.created_at || '')
        }
      } finally {
        setLoading(false)
      }
    }

    fetchProfile()
  }, [user])

  const validate = () => {
    const newErrors = {}
    if (!username.trim()) newErrors.username = 'Tên đăng nhập không được để trống'
    if (!email.trim()) {
      newErrors.email = 'Email không được để trống'
    } else if (!/\S+@\S+\.\S+/.test(email)) {
      newErrors.email = 'Email không đúng định dạng'
    }
    if (password && password.length < 6) {
      newErrors.password = 'Mật khẩu mới phải từ 6 ký tự trở lên'
    }
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSave = async (e) => {
    e.preventDefault()
    if (!validate()) return

    setSaving(true)
    try {
      const payload = {
        username: username.trim(),
        email: email.trim(),
        address: address.trim(),
      }
      if (password.trim()) {
        payload.password = password
      }

      const res = await updateProfile(payload)
      setUser(res.data)
      setPassword('') // Clear password field after saving
      toast.success('Đã cập nhật thông tin cá nhân thành công!')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Cập nhật thất bại. Vui lòng thử lại.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-[80vh] flex items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="p-4 sm:p-6 max-w-5xl mx-auto animate-fade-in">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Thông tin cá nhân</h1>
        <p className="text-sm text-gray-500">Quản lý và cập nhật thông tin tài khoản của bạn</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Card Overview */}
        <div className="lg:col-span-1">
          <div className="card p-6 flex flex-col items-center text-center">
            <div className="relative mb-4">
              <div className="w-24 h-24 rounded-full bg-primary-100 flex items-center justify-center border-4 border-white shadow-md">
                <span className="text-4xl font-bold text-primary-700">
                  {username?.[0]?.toUpperCase() || 'A'}
                </span>
              </div>
              <span className="absolute bottom-1 right-1 w-5.5 h-5.5 bg-success-500 border-2 border-white rounded-full flex items-center justify-center" title="Đang hoạt động">
                <span className="w-2.5 h-2.5 bg-white rounded-full animate-ping opacity-75" />
              </span>
            </div>

            <h2 className="text-lg font-bold text-gray-900 truncate max-w-full">{fullName}</h2>
            <p className="text-xs font-medium text-gray-400 mt-0.5">@{username}</p>
            
            <div className="mt-3 px-3 py-1 bg-primary-50 text-primary-700 text-xs font-semibold rounded-full border border-primary-100">
              Quản trị viên
            </div>

            <div className="w-full border-t border-gray-100 my-5 pt-4 text-left space-y-3.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-400">Email</span>
                <span className="font-semibold text-gray-700 truncate max-w-[150px]">{email}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-400">Quyền hạn</span>
                <span className="font-semibold text-gray-700">Tất cả quyền (Root)</span>
              </div>
              {createdAt && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-gray-400">Ngày tham gia</span>
                  <span className="font-semibold text-gray-700">{formatDate(createdAt)}</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column - Form Editor */}
        <div className="lg:col-span-2">
          <form onSubmit={handleSave} className="card p-6 space-y-6">
            <div>
              <h3 className="text-md font-bold text-gray-800 pb-3 border-b border-gray-100 flex items-center gap-2">
                <svg className="w-5 h-5 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
                Chỉnh sửa thông tin
              </h3>
            </div>

            {/* Editable fields */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="label">Tên đăng nhập</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className={`input ${errors.username ? 'input-error' : ''}`}
                  placeholder="Nhập tên đăng nhập"
                />
                {errors.username && <p className="error-msg">{errors.username}</p>}
              </div>

              <div>
                <label className="label">Email hệ thống</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={`input ${errors.email ? 'input-error' : ''}`}
                  placeholder="admin@creditintel.dev"
                />
                {errors.email && <p className="error-msg">{errors.email}</p>}
              </div>

              <div className="sm:col-span-2">
                <label className="label">Địa chỉ liên hệ</label>
                <input
                  type="text"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  className="input"
                  placeholder="Nhập địa chỉ của bạn"
                />
              </div>

              <div className="sm:col-span-2">
                <label className="label">
                  Mật khẩu mới <span className="text-gray-400 font-normal text-xs">(Để trống nếu không muốn đổi)</span>
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={`input ${errors.password ? 'input-error' : ''}`}
                  placeholder="••••••••"
                />
                {errors.password && <p className="error-msg">{errors.password}</p>}
              </div>
            </div>

            {/* Non-editable fields (Initially registered information) */}
            <div className="pt-4 border-t border-gray-100">
              <div className="mb-3 flex items-center gap-2">
                <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider">
                  Thông tin đăng ký ban đầu (Không thể chỉnh sửa)
                </h3>
                <span className="inline-flex items-center justify-center p-0.5 bg-gray-100 rounded text-gray-400" title="Trường dữ liệu được khóa bảo mật">
                  <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
                  </svg>
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="bg-gray-50 rounded-lg p-3 border border-gray-100 relative">
                  <span className="text-xs text-gray-400 block mb-1">Họ và tên</span>
                  <span className="text-sm font-semibold text-gray-700">{fullName}</span>
                </div>

                <div className="bg-gray-50 rounded-lg p-3 border border-gray-100 relative">
                  <span className="text-xs text-gray-400 block mb-1">Số điện thoại</span>
                  <span className="text-sm font-semibold text-gray-700">{phone}</span>
                </div>

                <div className="bg-gray-50 rounded-lg p-3 border border-gray-100 relative">
                  <span className="text-xs text-gray-400 block mb-1">CCCD / CMND</span>
                  <span className="text-sm font-semibold text-gray-700">{cccd}</span>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="pt-4 border-t border-gray-100 flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => navigate(-1)}
                className="btn-outline"
                disabled={saving}
              >
                Hủy bỏ
              </button>
              <button
                type="submit"
                className="btn-primary"
                disabled={saving}
              >
                {saving ? (
                  <>
                    <LoadingSpinner size="sm" className="mr-2 border-white" />
                    Đang lưu...
                  </>
                ) : (
                  'Lưu thay đổi'
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

export default AdminProfilePage
