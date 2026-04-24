import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  LineChart, Line, XAxis, YAxis, CartesianGrid, Legend,
} from 'recharts'
import { getDashboardSummary, getRiskDistribution, getAllApplications } from '../../../services/admin'
import useAuthStore from '../../../store/authStore'
import LoadingSpinner from '../../../components/common/LoadingSpinner'
import SummaryCard from '../../../components/admin/SummaryCard'
import { formatDate } from '../../../utils/format'

/* ── Palette cho Risk Pie Chart ────────────────── */
const RISK_COLORS = { LOW: '#22c55e', MEDIUM: '#f59e0b', HIGH: '#ef4444' }
const RISK_LABELS = { LOW: 'Thấp', MEDIUM: 'Trung bình', HIGH: 'Cao' }

/* ── Custom Pie label ──────────────────────────── */
const renderCustomLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, name, value }) => {
  const RADIAN = Math.PI / 180
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5
  const x = cx + radius * Math.cos(-midAngle * RADIAN)
  const y = cy + radius * Math.sin(-midAngle * RADIAN)
  return (
    <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" fontSize={12} fontWeight="bold">
      {value}
    </text>
  )
}

/* ── Group applications by date for line chart ── */
const groupByDate = (apps) => {
  const map = {}
  apps.forEach((a) => {
    const d = formatDate(a.submitted_at)
    map[d] = (map[d] || 0) + 1
  })
  return Object.entries(map)
    .map(([date, count]) => ({ date, count }))
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(-14) // last 14 days
}

const AdminDashboardPage = () => {
  const navigate = useNavigate()
  const user     = useAuthStore((s) => s.user)

  const [summary,  setSummary]  = useState(null)
  const [riskDist, setRiskDist] = useState([])
  const [trend,    setTrend]    = useState([])
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState(null)

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [sumRes, riskRes, appsRes] = await Promise.all([
          getDashboardSummary(),
          getRiskDistribution(),
          getAllApplications({ page: 1, limit: 100 }),
        ])
        setSummary(sumRes.data)
        setRiskDist(
          (riskRes.data || []).map((r) => ({
            name:  RISK_LABELS[r.risk_level] || r.risk_level,
            value: r.count,
            fill:  RISK_COLORS[r.risk_level] || '#94a3b8',
          }))
        )
        setTrend(groupByDate(appsRes.data?.items || []))
      } catch {
        setError('Không thể tải dữ liệu dashboard.')
      } finally {
        setLoading(false)
      }
    }
    fetchAll()
  }, [])

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <LoadingSpinner size="lg" />
    </div>
  )

  if (error) return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="card p-8 text-center max-w-sm w-full">
        <p className="text-danger-600 mb-4">{error}</p>
        <button onClick={() => window.location.reload()} className="btn-primary">Thử lại</button>
      </div>
    </div>
  )

  const cards = [
    {
      title:  'Tổng đơn hôm nay',
      value:  summary?.total_today,
      accent: 'primary',
      nav:    '/admin/applications',
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
        </svg>
      ),
    },
    {
      title:  'Đang chờ duyệt',
      value:  summary?.pending_review,
      accent: 'warning',
      nav:    '/admin/pending',
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
    {
      title:  'Đã duyệt hôm nay',
      value:  summary?.approved_today,
      accent: 'success',
      nav:    '/admin/applications?status=AWAITING_INFO',
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      ),
    },
    {
      title:  'Đã từ chối hôm nay',
      value:  summary?.rejected_today,
      accent: 'danger',
      nav:    '/admin/applications?status=ADMIN_REJECTED',
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      ),
    },
    {
      title:  'Tự động từ chối',
      value:  summary?.auto_rejected_today,
      accent: 'orange',
      nav:    '/admin/applications?status=AUTO_REJECTED',
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
      ),
    },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-500 mt-1">Xin chào, {user?.username} — Tổng quan hệ thống hôm nay</p>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
          {cards.map((c) => (
            <SummaryCard
              key={c.title}
              title={c.title}
              value={c.value}
              icon={c.icon}
              accent={c.accent}
              onClick={() => navigate(c.nav)}
            />
          ))}
        </div>

        {/* Charts row */}
        <div className="grid md:grid-cols-2 gap-6">
          {/* Pie — Risk Distribution */}
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Phân bố mức rủi ro</h2>
            {riskDist.length === 0 ? (
              <div className="flex items-center justify-center h-52 text-gray-400 text-sm">Không có dữ liệu</div>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={riskDist}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={90}
                    paddingAngle={3}
                    dataKey="value"
                    labelLine={false}
                    label={renderCustomLabel}
                  >
                    {riskDist.map((entry, i) => (
                      <Cell key={i} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(val, name) => [val, name]}
                    contentStyle={{ borderRadius: '0.75rem', border: '1px solid #e5e7eb', fontSize: 13 }}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
            {/* Legend */}
            <div className="flex justify-center gap-4 mt-2">
              {riskDist.map((r) => (
                <div key={r.name} className="flex items-center gap-1.5 text-sm text-gray-600">
                  <span className="w-3 h-3 rounded-full" style={{ backgroundColor: r.fill }} />
                  {r.name} ({r.value})
                </div>
              ))}
            </div>
          </div>

          {/* Line — Trend */}
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Xu hướng đơn vay</h2>
            {trend.length === 0 ? (
              <div className="flex items-center justify-center h-52 text-gray-400 text-sm">Không có dữ liệu</div>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={trend} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 11, fill: '#9ca3af' }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: '#9ca3af' }}
                    tickLine={false}
                    axisLine={false}
                    allowDecimals={false}
                  />
                  <Tooltip
                    contentStyle={{ borderRadius: '0.75rem', border: '1px solid #e5e7eb', fontSize: 13 }}
                    formatter={(val) => [val, 'Số đơn']}
                  />
                  <Line
                    type="monotone"
                    dataKey="count"
                    stroke="#2563eb"
                    strokeWidth={2}
                    dot={{ fill: '#2563eb', r: 3 }}
                    activeDot={{ r: 5 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default AdminDashboardPage
