/**
 * Mock API handlers.
 * Called by the axios mock adapter when VITE_MOCK_MODE=true.
 * Returns [status, data] tuples.
 */
import {
  MOCK_TOKEN, MOCK_USER, MOCK_APPS, MOCK_APP_STATUS,
  MOCK_PERSONAL_INFO_OUT, getNextChatResponse,
} from './mockData'

const delay = (ms) => new Promise((r) => setTimeout(r, ms))

// Active application based on configured status
const activeApp = () => ({ ...MOCK_APPS[MOCK_APP_STATUS] })

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
    return [200, { access_token: MOCK_TOKEN, token_type: 'bearer', user: MOCK_USER }]
  }

  /* ── Applications ─────────────────────────────────── */
  if (m === 'get' && url.endsWith('/applications/me')) {
    const app = activeApp()
    // Simulate "no active app" when status is a rejection
    if (app.status === 'AUTO_REJECTED' || app.status === 'ADMIN_REJECTED') {
      return [200, app] // still returns, dashboard handles display
    }
    return [200, app]
  }

  if (m === 'get' && /\/applications\/\d+$/.test(url)) {
    const id = parseInt(url.split('/').pop())
    const allApps = Object.values(MOCK_APPS)
    const found = allApps.find((a) => a.id === id) || activeApp()
    return [200, { ...found, id }]
  }

  if (m === 'post' && url.endsWith('/applications')) {
    // Simulate AI decision: credit_score < 600 or dti > 70 → AUTO_REJECTED
    const cs  = parseFloat(body.credit_score || 700)
    const dti = parseFloat(body.dti || 20)
    if (cs < 600 || dti > 70) {
      return [201, { ...MOCK_APPS.AUTO_REJECTED, ...body }]
    }
    return [201, { ...MOCK_APPS.PENDING_REVIEW, ...body }]
  }

  if (m === 'post' && /\/applications\/\d+\/personal-info$/.test(url)) {
    return [201, MOCK_PERSONAL_INFO_OUT]
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

  // Unmatched → 404
  return [404, { detail: `[Mock] No handler for ${m.toUpperCase()} ${url}` }]
}
