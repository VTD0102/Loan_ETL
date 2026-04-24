/**
 * Mock API handlers.
 * Called by the axios mock adapter when VITE_MOCK_MODE=true.
 * Returns [status, data] tuples.
 */
import {
  MOCK_TOKEN, MOCK_USER,
  MOCK_ADMIN_TOKEN, MOCK_ADMIN_USER, MOCK_ADMIN_APPS,
  MOCK_DASHBOARD_SUMMARY, MOCK_RISK_DISTRIBUTION, MOCK_PERSONAL_INFOS,
  getNextChatResponse
} from './mockData'

const delay = (ms) => new Promise((r) => setTimeout(r, ms))

const saveToStorage = () => {
  localStorage.setItem('MOCK_ADMIN_APPS', JSON.stringify(MOCK_ADMIN_APPS))
  localStorage.setItem('MOCK_PERSONAL_INFOS', JSON.stringify(MOCK_PERSONAL_INFOS))
}

export const mockHandlers = async (config) => {
  const { method, url, data: rawData } = config
  const m = method.toLowerCase()
  let body = {}
  try { body = typeof rawData === 'string' ? JSON.parse(rawData) : (rawData || {}) } catch { /**/ }

  await delay(350) // simulate network latency

  /* ── Auth ─────────────────────────────────────────── */
  if (m === 'post' && url.endsWith('/auth/register')) {
    return [201, { access_token: MOCK_TOKEN, token_type: 'bearer', user: MOCK_USER }]
  }

  if (m === 'post' && url.endsWith('/auth/login')) {
    if (body.email === 'wrong@test.com') {
      return [401, { detail: 'Sai email hoặc mật khẩu.' }]
    }
    // Admin login nếu email chứa 'admin'
    if (body.email?.includes('admin')) {
      return [200, { access_token: MOCK_ADMIN_TOKEN, token_type: 'bearer', user: MOCK_ADMIN_USER }]
    }
    return [200, { access_token: MOCK_TOKEN, token_type: 'bearer', user: MOCK_USER }]
  }

  /* ── Applications (Customer) ──────────────────────── */
  if (m === 'get' && url.endsWith('/applications/me')) {
    // Tìm đơn vay mới nhất của Customer (MOCK_USER.id = 1)
    const myApps = MOCK_ADMIN_APPS.filter((a) => a.user_id === MOCK_USER.id).sort((a, b) => b.id - a.id)
    if (myApps.length > 0) {
      return [200, myApps[0]]
    }
    // Chưa có đơn nào
    return [404, { detail: 'Not found' }]
  }

  if (m === 'get' && /\/applications\/\d+$/.test(url) && !url.includes('/admin/')) {
    const id = parseInt(url.split('/').pop())
    const found = MOCK_ADMIN_APPS.find((a) => a.id === id)
    if (found && found.user_id === MOCK_USER.id) return [200, found]
    return [404, { detail: 'Not found' }]
  }

  if (m === 'post' && url.endsWith('/applications')) {
    const cs  = parseFloat(body.credit_score || 700)
    const dti = parseFloat(body.dti || 20)
    const newId = Math.max(0, ...MOCK_ADMIN_APPS.map((a) => a.id)) + 1
    // Simulate AI decision
    const status = (cs < 600 || dti > 70) ? 'AUTO_REJECTED' : 'PENDING_REVIEW'
    
    const newApp = {
      id: newId,
      user_id: MOCK_USER.id,
      user_email: MOCK_USER.email,
      user_username: MOCK_USER.username,
      monthly_income: parseFloat(body.monthly_income || 0),
      loan_amount: parseFloat(body.loan_amount || 0),
      term: parseInt(body.term || 12),
      employment_status: body.employment_status || 'Employed',
      dti,
      is_homeowner: body.is_homeowner === 'true' || body.is_homeowner === true,
      listing_category: body.listing_category || 'Other',
      credit_score: cs,
      status,
      default_probability: status === 'AUTO_REJECTED' ? 0.8 : 0.15,
      risk_level: status === 'AUTO_REJECTED' ? 'HIGH' : 'LOW',
      risk_score: status === 'AUTO_REJECTED' ? 80 : 15,
      recommended_amount: status === 'AUTO_REJECTED' ? null : parseFloat(body.loan_amount || 0) * 0.9,
      recommended_term: status === 'AUTO_REJECTED' ? null : 36,
      submitted_at: new Date().toISOString(),
      reviewed_at: null,
      reviewed_by: null,
      admin_note: null
    }
    MOCK_ADMIN_APPS.unshift(newApp) // Push to top so Admin sees it first
    saveToStorage()
    return [201, newApp]
  }

  if (m === 'post' && /\/applications\/\d+\/personal-info$/.test(url) && !url.includes('/admin/')) {
    const id = parseInt(url.split('/')[url.split('/').indexOf('applications') + 1])
    const app = MOCK_ADMIN_APPS.find((a) => a.id === id)
    if (app && app.user_id === MOCK_USER.id) {
      app.status = 'INFO_SUBMITTED' // Update status
      
      // Save personal info
      const newInfo = {
        ...body,
        id: Math.max(0, ...MOCK_PERSONAL_INFOS.map((i) => i.id)) + 1,
        application_id: id,
        user_id: MOCK_USER.id,
        email: MOCK_USER.email,
        submitted_at: new Date().toISOString()
      }
      MOCK_PERSONAL_INFOS.push(newInfo)
      saveToStorage()
      return [201, newInfo]
    }
    return [404, { detail: 'Application not found' }]
  }

  /* ── Chat ─────────────────────────────────────────── */
  if (m === 'post' && url.endsWith('/chat')) {
    await delay(600) // extra delay to simulate LLM
    return [200, { reply: getNextChatResponse() }]
  }

  if (m === 'get' && url.endsWith('/chat/sessions')) {
    return [200, []]
  }

  /* ── Health ──────────────────────────────────────── */
  if (m === 'get' && url.endsWith('/health')) {
    return [200, { status: 'ok (mock mode)' }]
  }

  /* ── Admin — Dashboard ───────────────────────────── */
  if (m === 'get' && url.endsWith('/admin/dashboard/summary')) {
    // Calculate dynamically based on MOCK_ADMIN_APPS for "realism"
    const today = new Date().toISOString().split('T')[0]
    const summary = {
      total_today: MOCK_ADMIN_APPS.filter(a => a.submitted_at.startsWith(today)).length,
      pending_review: MOCK_ADMIN_APPS.filter(a => a.status === 'PENDING_REVIEW').length,
      approved_today: MOCK_ADMIN_APPS.filter(a => ['AWAITING_INFO', 'INFO_SUBMITTED'].includes(a.status) && a.reviewed_at?.startsWith(today)).length,
      rejected_today: MOCK_ADMIN_APPS.filter(a => a.status === 'ADMIN_REJECTED' && a.reviewed_at?.startsWith(today)).length,
      auto_rejected_today: MOCK_ADMIN_APPS.filter(a => a.status === 'AUTO_REJECTED' && a.submitted_at.startsWith(today)).length,
    }
    // Fallback to static mock if dynamic is 0 (for empty demo days)
    return [200, summary.total_today > 0 ? summary : MOCK_DASHBOARD_SUMMARY]
  }

  if (m === 'get' && url.endsWith('/admin/dashboard/risk-distribution')) {
    return [200, MOCK_RISK_DISTRIBUTION]
  }

  /* ── Admin — Applications ────────────────────────── */
  if (m === 'get' && url.includes('/admin/applications/pending')) {
    const params = new URL('http://x?' + (url.split('?')[1] || '')).searchParams
    const page  = parseInt(params.get('page') || '1')
    const limit = parseInt(params.get('limit') || '20')
    const pending = MOCK_ADMIN_APPS.filter(a => a.status === 'PENDING_REVIEW')
    const start = (page - 1) * limit
    return [200, {
      items: pending.slice(start, start + limit),
      total: pending.length,
      page,
      limit,
      pages: Math.ceil(pending.length / limit) || 1,
    }]
  }

  if (m === 'get' && url.includes('/admin/applications') && !url.match(/\/admin\/applications\/\d+/)) {
    const params = new URL('http://x?' + (url.split('?')[1] || '')).searchParams
    const page       = parseInt(params.get('page') || '1')
    const limit      = parseInt(params.get('limit') || '20')
    const status     = params.get('status')
    const riskLevel  = params.get('risk_level')
    const fromDate   = params.get('from_date')
    const toDate     = params.get('to_date')

    let apps = [...MOCK_ADMIN_APPS]
    if (status)    apps = apps.filter(a => a.status === status)
    if (riskLevel) apps = apps.filter(a => a.risk_level === riskLevel)
    if (fromDate)  apps = apps.filter(a => a.submitted_at >= fromDate)
    if (toDate)    apps = apps.filter(a => a.submitted_at <= toDate + 'T23:59:59')

    const start = (page - 1) * limit
    return [200, {
      items: apps.slice(start, start + limit),
      total: apps.length,
      page,
      limit,
      pages: Math.ceil(apps.length / limit) || 1,
    }]
  }

  if (m === 'get' && /\/admin\/applications\/\d+\/personal-info$/.test(url)) {
    const id = parseInt(url.split('/')[url.split('/').indexOf('applications') + 1])
    const info = MOCK_PERSONAL_INFOS.find((i) => i.application_id === id)
    if (info) return [200, info]
    return [404, { detail: 'Khách hàng chưa nộp thông tin cá nhân.' }]
  }

  if (m === 'get' && /\/admin\/applications\/\d+$/.test(url)) {
    const id = parseInt(url.split('/').pop())
    const found = MOCK_ADMIN_APPS.find(a => a.id === id)
    if (found) return [200, found]
    return [404, { detail: 'Không tìm thấy đơn vay.' }]
  }

  if (m === 'post' && /\/admin\/applications\/\d+\/approve$/.test(url)) {
    const id = parseInt(url.split('/').slice(-2)[0])
    const app = MOCK_ADMIN_APPS.find(a => a.id === id)
    if (!app) return [404, { detail: 'Không tìm thấy đơn vay.' }]
    app.status      = 'AWAITING_INFO'
    app.reviewed_at = new Date().toISOString()
    app.reviewed_by = MOCK_ADMIN_USER.email
    saveToStorage()
    return [200, app]
  }

  if (m === 'post' && /\/admin\/applications\/\d+\/reject$/.test(url)) {
    const id = parseInt(url.split('/').slice(-2)[0])
    const app = MOCK_ADMIN_APPS.find(a => a.id === id)
    if (!app) return [404, { detail: 'Không tìm thấy đơn vay.' }]
    app.status      = 'ADMIN_REJECTED'
    app.admin_note  = body.reason || body.admin_note || 'Đã từ chối.'
    app.reviewed_at = new Date().toISOString()
    app.reviewed_by = MOCK_ADMIN_USER.email
    saveToStorage()
    return [200, app]
  }

  // Unmatched → 404
  return [404, { detail: `[Mock] No handler for ${m.toUpperCase()} ${url}` }]

}
