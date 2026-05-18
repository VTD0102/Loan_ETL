import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
} from 'recharts'
import { getRiskDistribution, getAllApplications } from '../../../services/admin'
import useAuthStore from '../../../store/authStore'
import LoadingSpinner from '../../../components/common/LoadingSpinner'
import SummaryCard from '../../../components/admin/SummaryCard'
import { RiskBadge, StatusBadge } from '../../../components/common/Badge'
import { formatCurrency, formatDate } from '../../../utils/format'

const RISK_COLORS = {
  LOW: '#16a34a',
  MEDIUM: '#d97706',
  HIGH: '#dc2626',
  UNASSIGNED: '#64748b',
}

const RISK_LABELS = {
  LOW: 'Thấp',
  MEDIUM: 'Trung bình',
  HIGH: 'Cao',
  UNASSIGNED: 'Chưa chấm',
}

const RISK_ORDER = ['LOW', 'MEDIUM', 'HIGH', 'UNASSIGNED']

const normalizeRiskLevel = (level) => {
  const value = String(level || 'UNASSIGNED').trim().toUpperCase()
  if (['LOW', 'THAP', 'THẤP'].includes(value)) return 'LOW'
  if (['MEDIUM', 'TRUNG BINH', 'TRUNG BÌNH'].includes(value)) return 'MEDIUM'
  if (['HIGH', 'CAO'].includes(value)) return 'HIGH'
  return 'UNASSIGNED'
}

const getFriendlyApplicationCode = (id) => {
  const compactId = String(id || '').replaceAll('-', '').toUpperCase()
  return `APP-${compactId.slice(-6) || 'NEW'}`
}

const renderCustomLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, value }) => {
  if (!value) return null
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5
  const x = cx + radius * Math.cos(-midAngle * (Math.PI / 180))
  const y = cy + radius * Math.sin(-midAngle * (Math.PI / 180))
  return (
    <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" fontSize={12} fontWeight="700">
      {value}
    </text>
  )
}

const groupByDate = (apps) => {
  const map = {}
  apps.forEach((app) => {
    if (!app.submitted_at) return
    const key = app.submitted_at.slice(0, 10)
    map[key] = (map[key] || 0) + 1
  })
  return Object.entries(map)
    .map(([key, count]) => ({ key, date: formatDate(key), count }))
    .sort((a, b) => a.key.localeCompare(b.key))
    .slice(-14)
}

const sortBySubmittedAt = (apps) =>
  [...apps].sort((a, b) => new Date(b.submitted_at || 0) - new Date(a.submitted_at || 0))

const MetricRow = ({ label, value, tone = 'primary', onClick }) => {
  const toneClass = {
    primary: 'bg-primary-50 text-primary-700 border-primary-100',
    warning: 'bg-warning-50 text-warning-700 border-warning-100',
    danger: 'bg-danger-50 text-danger-700 border-danger-100',
    success: 'bg-success-50 text-success-700 border-success-100',
    gray: 'bg-gray-50 text-gray-700 border-gray-200',
  }[tone]

  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-center justify-between rounded-lg border px-4 py-3 text-left transition hover:-translate-y-0.5 hover:shadow-sm ${toneClass}`}
    >
      <span className="text-sm font-medium">{label}</span>
      <span className="text-xl font-bold">{value}</span>
    </button>
  )
}

const AdminDashboardPage = () => {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)

  const [riskDist, setRiskDist] = useState([])
  const [trend, setTrend] = useState([])
  const [apps, setApps] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [riskRes, appsRes] = await Promise.all([
          getRiskDistribution(),
          getAllApplications({ page: 1, limit: 100 }),
        ])
        const allApps = appsRes.data?.items || []
        setApps(allApps)
        setTrend(groupByDate(allApps))
        const groupedRisk = (riskRes.data || []).reduce((acc, item) => {
          const level = normalizeRiskLevel(item.risk_level)
          acc[level] = (acc[level] || 0) + Number(item.count || 0)
          return acc
        }, {})
        setRiskDist(
          Object.entries(groupedRisk).map(([level, value]) => ({
            level,
            name: RISK_LABELS[level],
            value,
            fill: RISK_COLORS[level],
          })).sort((a, b) => RISK_ORDER.indexOf(a.level) - RISK_ORDER.indexOf(b.level))
        )
      } catch {
        setError('Không thể tải dữ liệu dashboard.')
      } finally {
        setLoading(false)
      }
    }
    fetchAll()
  }, [])

  const dashboardStats = useMemo(() => {
    const pending = apps.filter((app) => app.status === 'PENDING_REVIEW')
    const approved = apps.filter((app) => ['APPROVED', 'AWAITING_INFO', 'INFO_SUBMITTED'].includes(app.status))
    const rejected = apps.filter((app) => ['ADMIN_REJECTED', 'REJECTED'].includes(app.status))
    const autoRejected = apps.filter((app) => app.status === 'AUTO_REJECTED')
    const highRiskPending = pending.filter((app) => normalizeRiskLevel(app.risk_level) === 'HIGH')
    const mediumRiskPending = pending.filter((app) => normalizeRiskLevel(app.risk_level) === 'MEDIUM')
    const unassigned = apps.filter((app) => normalizeRiskLevel(app.risk_level) === 'UNASSIGNED')
    const scored = apps.filter((app) => app.risk_score !== null && app.risk_score !== undefined)
    const avgRiskScore = scored.length
      ? Math.round(scored.reduce((sum, app) => sum + Number(app.risk_score || 0), 0) / scored.length)
      : null

    return {
      pending,
      approved,
      rejected,
      autoRejected,
      highRiskPending,
      mediumRiskPending,
      unassigned,
      avgRiskScore,
      recent: sortBySubmittedAt(apps).slice(0, 6),
      reviewLoad: pending.length + unassigned.length,
    }
  }, [apps])

  if (loading) return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <LoadingSpinner size="lg" />
    </div>
  )

  if (error) return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="card w-full max-w-sm p-8 text-center">
        <p className="mb-4 text-danger-600">{error}</p>
        <button onClick={() => window.location.reload()} className="btn-primary">Thử lại</button>
      </div>
    </div>
  )

  const riskTotal = riskDist.reduce((sum, item) => sum + item.value, 0)

  const cards = [
    {
      title: 'Tổng hồ sơ',
      value: apps.length,
      subtitle: 'Toàn bộ hồ sơ trong hệ thống',
      accent: 'primary',
      nav: '/admin/applications',
      icon: (
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
        </svg>
      ),
    },
    {
      title: 'Đang chờ duyệt',
      value: dashboardStats.pending.length,
      subtitle: 'Cần admin ra quyết định',
      accent: 'warning',
      nav: '/admin/pending',
      icon: (
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
    {
      title: 'Đã duyệt',
      value: dashboardStats.approved.length,
      subtitle: 'Đã qua bước xét duyệt',
      accent: 'success',
      nav: '/admin/applications?status=APPROVED',
      icon: (
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      ),
    },
    {
      title: 'Đã từ chối',
      value: dashboardStats.rejected.length,
      subtitle: 'Admin từ chối sau rà soát',
      accent: 'danger',
      nav: '/admin/applications?status=ADMIN_REJECTED',
      icon: (
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      ),
    },
    {
      title: 'Tự động từ chối',
      value: dashboardStats.autoRejected.length,
      subtitle: 'Model chặn hồ sơ rủi ro cao',
      accent: 'orange',
      nav: '/admin/applications?status=AUTO_REJECTED',
      icon: (
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
      ),
    },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <div className="mb-8 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-primary-600">Admin workspace</p>
            <h1 className="mt-2 text-3xl font-bold text-gray-950">Dashboard xét duyệt</h1>
            <p className="mt-2 text-gray-500">Xin chào, {user?.username || 'admin'} — theo dõi luồng hồ sơ, rủi ro và việc cần xử lý.</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button onClick={() => navigate('/admin/pending')} className="btn-primary">
              Xem đơn chờ duyệt
            </button>
            <button onClick={() => navigate('/admin/applications')} className="btn-outline">
              Tất cả hồ sơ
            </button>
          </div>
        </div>

        <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {cards.map((card) => (
            <SummaryCard
              key={card.title}
              title={card.title}
              value={card.value}
              subtitle={card.subtitle}
              icon={card.icon}
              accent={card.accent}
              onClick={() => navigate(card.nav)}
            />
          ))}
        </div>

        <div className="mb-6 grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
          <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-950">Ưu tiên xử lý</h2>
                <p className="mt-1 text-sm text-gray-500">Tập trung vào hồ sơ chờ duyệt và hồ sơ chưa có chấm điểm rủi ro.</p>
              </div>
              <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-semibold text-gray-600">
                {dashboardStats.reviewLoad} việc cần xem
              </span>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <MetricRow
                label="Chờ duyệt"
                value={dashboardStats.pending.length}
                tone="warning"
                onClick={() => navigate('/admin/pending')}
              />
              <MetricRow
                label="Pending rủi ro cao"
                value={dashboardStats.highRiskPending.length}
                tone="danger"
                onClick={() => navigate('/admin/applications?status=PENDING_REVIEW&risk_level=HIGH')}
              />
              <MetricRow
                label="Pending trung bình"
                value={dashboardStats.mediumRiskPending.length}
                tone="warning"
                onClick={() => navigate('/admin/applications?status=PENDING_REVIEW&risk_level=MEDIUM')}
              />
              <MetricRow
                label="Chưa chấm rủi ro"
                value={dashboardStats.unassigned.length}
                tone="gray"
                onClick={() => navigate('/admin/applications')}
              />
            </div>
          </section>

          <section className="rounded-xl border border-primary-100 bg-white p-6 shadow-sm">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-gray-950">Sức khỏe hàng đợi</h2>
                <p className="mt-1 text-sm text-gray-500">Tổng quan nhanh để biết dashboard đang cần chú ý ở đâu.</p>
              </div>
              <div className="rounded-xl bg-primary-50 px-4 py-3 text-right">
                <p className="text-xs font-medium text-primary-700">Risk score TB</p>
                <p className="mt-1 text-2xl font-bold text-primary-700">{dashboardStats.avgRiskScore ?? '—'}</p>
              </div>
            </div>
            <div className="mt-6 space-y-4">
              <div>
                <div className="mb-1 flex justify-between text-xs font-medium text-gray-500">
                  <span>Tải xử lý</span>
                  <span>{dashboardStats.pending.length}/{apps.length || 1} hồ sơ</span>
                </div>
                <div className="h-2 rounded-full bg-gray-100">
                  <div
                    className="h-2 rounded-full bg-warning-500"
                    style={{ width: `${Math.min((dashboardStats.pending.length / Math.max(apps.length, 1)) * 100, 100)}%` }}
                  />
                </div>
              </div>
              <div>
                <div className="mb-1 flex justify-between text-xs font-medium text-gray-500">
                  <span>Hồ sơ rủi ro cao đang chờ</span>
                  <span>{dashboardStats.highRiskPending.length}</span>
                </div>
                <div className="h-2 rounded-full bg-gray-100">
                  <div
                    className="h-2 rounded-full bg-danger-500"
                    style={{ width: `${Math.min((dashboardStats.highRiskPending.length / Math.max(dashboardStats.pending.length, 1)) * 100, 100)}%` }}
                  />
                </div>
              </div>
            </div>
          </section>
        </div>

        <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
          <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-gray-950">Phân bố mức rủi ro</h2>
                <p className="mt-1 text-sm text-gray-500">Tổng {riskTotal} hồ sơ theo nhãn ML hiện có.</p>
              </div>
            </div>
            {riskDist.length === 0 ? (
              <div className="flex h-64 items-center justify-center text-sm text-gray-400">Không có dữ liệu</div>
            ) : (
              <div className="grid items-center gap-4 md:grid-cols-[1fr_180px]">
                <ResponsiveContainer width="100%" height={250}>
                  <PieChart>
                    <Pie
                      data={riskDist}
                      cx="50%"
                      cy="50%"
                      innerRadius={58}
                      outerRadius={96}
                      paddingAngle={3}
                      dataKey="value"
                      labelLine={false}
                      label={renderCustomLabel}
                    >
                      {riskDist.map((entry) => (
                        <Cell key={entry.level} fill={entry.fill} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value, name) => [`${value} hồ sơ`, name]}
                      contentStyle={{ borderRadius: '0.75rem', border: '1px solid #e5e7eb', fontSize: 13 }}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <div className="space-y-3">
                  {riskDist.map((item) => {
                    const pct = riskTotal ? Math.round((item.value / riskTotal) * 100) : 0
                    return (
                      <div key={item.level}>
                        <div className="mb-1 flex items-center justify-between text-sm">
                          <span className="flex items-center gap-2 text-gray-600">
                            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.fill }} />
                            {item.name}
                          </span>
                          <span className="font-semibold text-gray-900">{item.value}</span>
                        </div>
                        <div className="h-1.5 rounded-full bg-gray-100">
                          <div className="h-1.5 rounded-full" style={{ width: `${pct}%`, backgroundColor: item.fill }} />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </section>

          <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-gray-950">Xu hướng đơn vay</h2>
                <p className="mt-1 text-sm text-gray-500">Số hồ sơ nộp theo ngày trong dữ liệu gần nhất.</p>
              </div>
            </div>
            {trend.length === 0 ? (
              <div className="flex h-64 items-center justify-center text-sm text-gray-400">Không có dữ liệu</div>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={trend} margin={{ top: 8, right: 16, left: -18, bottom: 0 }}>
                  <defs>
                    <linearGradient id="loanTrend" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#2563eb" stopOpacity={0.22} />
                      <stop offset="95%" stopColor="#2563eb" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{ borderRadius: '0.75rem', border: '1px solid #e5e7eb', fontSize: 13 }}
                    formatter={(value) => [`${value} hồ sơ`, 'Số đơn']}
                  />
                  <Area
                    type="monotone"
                    dataKey="count"
                    stroke="#2563eb"
                    strokeWidth={2.5}
                    fill="url(#loanTrend)"
                    dot={{ fill: '#2563eb', r: 3 }}
                    activeDot={{ r: 5 }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </section>
        </div>

        <section className="mt-6 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-950">Hồ sơ mới nhất</h2>
              <p className="mt-1 text-sm text-gray-500">Danh sách rút gọn để admin mở chi tiết ngay từ dashboard.</p>
            </div>
            <button onClick={() => navigate('/admin/applications')} className="btn-outline text-sm">
              Xem tất cả
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                  <th className="px-3 py-3">Mã hồ sơ</th>
                  <th className="px-3 py-3">Khách hàng</th>
                  <th className="px-3 py-3 text-right">Số tiền</th>
                  <th className="px-3 py-3 text-center">Rủi ro</th>
                  <th className="px-3 py-3 text-center">Trạng thái</th>
                  <th className="px-3 py-3 text-right">Ngày nộp</th>
                  <th className="px-3 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {dashboardStats.recent.map((app) => (
                  <tr key={app.id} className="transition hover:bg-gray-50">
                    <td className="px-3 py-3">
                      <span className="inline-flex rounded-md bg-gray-50 px-2 py-1 text-xs font-semibold text-gray-600 ring-1 ring-inset ring-gray-200">
                        {getFriendlyApplicationCode(app.id)}
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <p className="max-w-[190px] truncate font-medium text-gray-900">{app.user_email || app.user_username || 'Khách hàng'}</p>
                    </td>
                    <td className="px-3 py-3 text-right font-semibold text-gray-900">{formatCurrency(app.loan_amount)}</td>
                    <td className="px-3 py-3 text-center">
                      {normalizeRiskLevel(app.risk_level) === 'UNASSIGNED'
                        ? <span className="text-xs text-gray-400">Chưa chấm</span>
                        : <RiskBadge level={normalizeRiskLevel(app.risk_level)} />}
                    </td>
                    <td className="px-3 py-3 text-center">
                      <StatusBadge status={app.status} />
                    </td>
                    <td className="px-3 py-3 text-right text-xs text-gray-500">{formatDate(app.submitted_at)}</td>
                    <td className="px-3 py-3 text-right">
                      <button
                        onClick={() => navigate(`/admin/application/${app.id}`)}
                        className="btn-outline px-3 py-1.5 text-xs"
                      >
                        Mở
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  )
}

export default AdminDashboardPage
