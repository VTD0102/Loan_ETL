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
const MOCK_CHAT_SESSION_ID = '00000000-0000-4000-8000-000000000001'
const MOCK_CHAT_HISTORY_KEY = 'MOCK_CHAT_HISTORY'
const MOCK_CHAT_PENDING_ACTION_KEY = 'MOCK_CHAT_PENDING_ACTION'

const saveToStorage = () => {
  localStorage.setItem('MOCK_ADMIN_APPS', JSON.stringify(MOCK_ADMIN_APPS))
  localStorage.setItem('MOCK_PERSONAL_INFOS', JSON.stringify(MOCK_PERSONAL_INFOS))
}

const getMockChatHistory = () => {
  try {
    return JSON.parse(localStorage.getItem(MOCK_CHAT_HISTORY_KEY) || '[]')
  } catch {
    return []
  }
}

const saveMockChatHistory = (messages) => {
  localStorage.setItem(MOCK_CHAT_HISTORY_KEY, JSON.stringify(messages))
}

const getMockPendingAction = () => {
  try {
    return JSON.parse(localStorage.getItem(MOCK_CHAT_PENDING_ACTION_KEY) || 'null')
  } catch {
    return null
  }
}

const saveMockPendingAction = (action) => {
  if (!action) {
    localStorage.removeItem(MOCK_CHAT_PENDING_ACTION_KEY)
    return
  }
  localStorage.setItem(MOCK_CHAT_PENDING_ACTION_KEY, JSON.stringify(action))
}

const createMockPendingAction = () => ({
  type: 'loan_term_adjustment',
  status: 'pending_confirmation',
  source_application_id: 'mock-auto-rejected-application',
  created_at: new Date().toISOString(),
  expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
  proposal: {
    loan_amount: '12000',
    term: 36,
    default_probability: 0.285,
    risk_level: 'LOW',
    risk_score: 28,
    model_version: 'mock-model',
  },
  proposals: [
    {
      loan_amount: '12000',
      term: 36,
      default_probability: 0.285,
      risk_level: 'LOW',
      risk_score: 28,
      model_version: 'mock-model',
    },
    {
      loan_amount: '10000',
      term: 24,
      default_probability: 0.31,
      risk_level: 'MEDIUM',
      risk_score: 31,
      model_version: 'mock-model',
    },
    {
      loan_amount: '8000',
      term: 12,
      default_probability: 0.37,
      risk_level: 'MEDIUM',
      risk_score: 37,
      model_version: 'mock-model',
    },
  ],
})

const mockPrediction = (body) => {
  const dtiRaw = parseFloat(body.dti || 0)
  const dti = dtiRaw > 1 ? dtiRaw / 100 : dtiRaw
  const income = parseFloat(body.monthly_income || 0)
  const loan = parseFloat(body.loan_amount || 0)
  const term = parseInt(body.term || 36)
  const paymentToIncome = income > 0 && term > 0 ? (loan / term) / income : 0
  const badDebtPenalty = body.has_bad_debt === true || body.has_bad_debt === 'true' ? 0.18 : 0
  const prob = Math.min(0.85, Math.max(0.03, 0.05 + dti * 0.35 + paymentToIncome * 0.9 + badDebtPenalty))
  const status = prob > 0.4 ? 'AUTO_REJECTED' : 'PENDING_REVIEW'
  return {
    status,
    default_probability: Number(prob.toFixed(4)),
    risk_level: prob > 0.4 ? 'High' : prob > 0.2 ? 'Medium' : 'Low',
    risk_score: Math.round((1 - prob) * 100),
    is_perfect_fit: prob < 0.2,
    suggested_amount: status === 'AUTO_REJECTED' ? Math.round(loan * 0.75) : Math.round(loan * 0.9),
    suggested_term: status === 'AUTO_REJECTED' ? 60 : term,
    model_version: 'mock_lgbm_v4_stability',
  }
}

const scoreBand = (score) => {
  if (score >= 740) return 'Excellent'
  if (score >= 670) return 'Good'
  if (score >= 580) return 'Fair'
  return 'Poor'
}

const mockScorecard = (app) => {
  const prob = Number(app.default_probability ?? mockPrediction(app).default_probability)
  const score = Math.max(300, Math.min(850, Math.round(820 - prob * 650)))
  return {
    member_key: String(app.user_id || MOCK_USER.id),
    credit_score: score,
    score_band: scoreBand(score),
    default_probability: prob,
    risk_level: prob > 0.4 ? 'High' : prob > 0.2 ? 'Medium' : 'Low',
    top_factors: [
      {
        feature: 'payment_to_income',
        direction: prob > 0.2 ? 'increases_risk' : 'decreases_risk',
        impact: Number((prob * 0.8).toFixed(4)),
      },
      {
        feature: 'has_bad_debt',
        direction: app.has_bad_debt ? 'increases_risk' : 'decreases_risk',
        impact: app.has_bad_debt ? 0.22 : -0.08,
      },
      {
        feature: 'income_verifiable_flag',
        direction: app.income_verifiable_flag ? 'decreases_risk' : 'increases_risk',
        impact: app.income_verifiable_flag ? -0.12 : 0.1,
      },
    ],
  }
}

const buildMockApplication = (body, prediction) => ({
  id: Math.max(0, ...MOCK_ADMIN_APPS.map((a) => a.id)) + 1,
  user_id: MOCK_USER.id,
  user_email: MOCK_USER.email,
  user_username: MOCK_USER.username,
  monthly_income: parseFloat(body.monthly_income || 0),
  loan_amount: parseFloat(body.loan_amount || 0),
  term: parseInt(body.term || 12),
  employment_status: body.employment_status || 'Employed',
  dti: parseFloat(body.dti || 0),
  is_homeowner: body.is_homeowner === 'true' || body.is_homeowner === true,
  listing_category: body.listing_category || 'Other',
  credit_score: body.credit_score ?? null,
  occupation_type: body.occupation_type || 'OTHER',
  years_employed: parseFloat(body.years_employed || 0),
  num_bureau_records: parseInt(body.num_bureau_records || 0),
  num_active_credit: parseInt(body.num_active_credit || 0),
  total_overdue_amount: parseFloat(body.total_overdue_amount || 0),
  max_credit_overdue_days: parseInt(body.max_credit_overdue_days || 0),
  has_bad_debt: body.has_bad_debt === 'true' || body.has_bad_debt === true,
  income_verifiable_flag: body.income_verifiable_flag === 'true' || body.income_verifiable_flag === true,
  age_years: parseInt(body.age_years || 0),
  education_ordinal: parseInt(body.education_ordinal || 3),
  is_married_flag: body.is_married_flag === 'true' || body.is_married_flag === true,
  status: prediction.status,
  default_probability: prediction.default_probability,
  risk_level: prediction.risk_level,
  risk_score: prediction.risk_score,
  recommended_amount: prediction.suggested_amount,
  recommended_term: prediction.suggested_term,
  model_version: prediction.model_version,
  submitted_at: new Date().toISOString(),
  reviewed_at: null,
  reviewed_by: null,
  admin_note: null
})

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

  if (m === 'get' && url.endsWith('/auth/me')) {
    const authHeader = config.headers?.Authorization || ''
    if (authHeader.includes(MOCK_ADMIN_TOKEN)) {
      return [200, MOCK_ADMIN_USER]
    }
    return [200, MOCK_USER]
  }

  if (m === 'put' && url.endsWith('/auth/profile')) {
    const authHeader = config.headers?.Authorization || ''
    if (authHeader.includes(MOCK_ADMIN_TOKEN)) {
      if (body.username !== undefined) MOCK_ADMIN_USER.username = body.username
      if (body.email !== undefined) MOCK_ADMIN_USER.email = body.email
      if (body.address !== undefined) MOCK_ADMIN_USER.address = body.address
      return [200, MOCK_ADMIN_USER]
    } else {
      if (body.username !== undefined) MOCK_USER.username = body.username
      if (body.email !== undefined) MOCK_USER.email = body.email
      if (body.address !== undefined) MOCK_USER.address = body.address
      return [200, MOCK_USER]
    }
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

  if (m === 'get' && /\/applications\/\d+$/.test(url) && !url.includes('/admin/') && !url.includes('/credit-score/')) {
    const id = parseInt(url.split('/').pop())
    const found = MOCK_ADMIN_APPS.find((a) => a.id === id)
    if (found && found.user_id === MOCK_USER.id) return [200, found]
    return [404, { detail: 'Not found' }]
  }

  if (m === 'get' && /\/credit-score\/applications\/\d+$/.test(url)) {
    const id = parseInt(url.split('/').pop())
    const found = MOCK_ADMIN_APPS.find((a) => a.id === id)
    if (found && found.user_id === MOCK_USER.id) return [200, mockScorecard(found)]
    return [404, { detail: 'Application not found' }]
  }

  if (m === 'get' && /\/credit-score\/admin\/applications\/\d+$/.test(url)) {
    const id = parseInt(url.split('/').pop())
    const found = MOCK_ADMIN_APPS.find((a) => a.id === id)
    if (found) return [200, mockScorecard(found)]
    return [404, { detail: 'Application not found' }]
  }

  if (m === 'post' && url.endsWith('/applications/evaluate')) {
    const prediction = mockPrediction(body)
    return [200, { ...prediction, application_id: null }]
  }

  if (m === 'post' && (url.endsWith('/applications/confirm') || url.endsWith('/applications'))) {
    const prediction = mockPrediction(body)
    const newApp = buildMockApplication(body, prediction)
    MOCK_ADMIN_APPS.unshift(newApp) // Push to top so Admin sees it first
    saveToStorage()
    return [200, {
      application_id: String(newApp.id),
      status: newApp.status,
      default_probability: newApp.default_probability,
      risk_level: newApp.risk_level,
      risk_score: newApp.risk_score,
      suggested_amount: newApp.recommended_amount,
      suggested_term: newApp.recommended_term,
    }]
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
    const message = body.message || ''
    const normalizedMessage = message.toLowerCase()
    const wantsAdjustment = /gói vay|goi vay|phương án|phuong an|đổi kỳ hạn|doi ky han|nộp lại|nop lai|bị từ chối|bi tu choi/.test(normalizedMessage)
    const confirmsAdjustment = /xác nhận|xac nhan|đồng ý|dong y|^ok$/.test(normalizedMessage.trim())
    const cancelsAdjustment = /hủy|huy|không|khong/.test(normalizedMessage)
    let pendingAction = getMockPendingAction()
    let reply = getNextChatResponse()

    if (confirmsAdjustment && pendingAction) {
      const optionMatch = normalizedMessage.match(/(?:phương án|phuong an|gói|goi)\s+([123])/)
      const selectedIndex = optionMatch ? Number(optionMatch[1]) - 1 : 0
      const selected = pendingAction.proposals?.[selectedIndex] || pendingAction.proposal
      reply = `Đã nộp lại hồ sơ mới với số tiền ${selected.loan_amount} và kỳ hạn ${selected.term} tháng. Trạng thái hiện tại: PENDING_REVIEW.`
      pendingAction = null
    } else if (cancelsAdjustment && pendingAction) {
      reply = 'Mình đã hủy phương án nộp lại đang chờ xác nhận. Hồ sơ bị từ chối cũ không bị thay đổi.'
      pendingAction = null
    } else if (wantsAdjustment) {
      pendingAction = createMockPendingAction()
      reply = 'Mình đã tìm được 3 khoản vay phù hợp. Chọn một phương án bên dưới, sau đó bấm đồng ý để mình nộp lại hồ sơ mới.'
    }

    saveMockPendingAction(pendingAction)
    const history = getMockChatHistory()
    const nextHistory = [
      ...history,
      { role: 'user', content: message },
      { role: 'assistant', content: reply, sources: [] },
    ]
    saveMockChatHistory(nextHistory)
    return [200, { response: reply, reply, session_id: MOCK_CHAT_SESSION_ID, sources: [], pending_action: pendingAction }]
  }

  if (m === 'get' && url.includes('/chat/history')) {
    return [200, { session_id: MOCK_CHAT_SESSION_ID, messages: getMockChatHistory(), pending_action: getMockPendingAction() }]
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
