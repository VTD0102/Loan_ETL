// Fake JWT (valid structure, not verified by frontend)
export const MOCK_TOKEN =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9' +
  '.eyJzdWIiOiIxIiwiZXhwIjo5OTk5OTk5OTk5LCJyb2xlIjoiY3VzdG9tZXIifQ' +
  '.mock_signature_for_testing_only'

export const MOCK_USER = {
  id:         1,
  email:      'testcustomer@creditintel.dev',
  username:   'TestCustomer',
  role:       'customer',
  created_at: '2025-01-15T08:00:00',
}

// Pre-built applications covering all 5 statuses.
// Change MOCK_APP_STATUS below to switch which state the dashboard shows.
export const MOCK_APP_STATUS = 'AWAITING_INFO'
// Options: 'PENDING_REVIEW' | 'AUTO_REJECTED' | 'ADMIN_REJECTED' | 'AWAITING_INFO' | 'INFO_SUBMITTED'

const base = {
  id:                1,
  user_id:           1,
  monthly_income:    6500,
  loan_amount:       15000,
  term:              36,
  employment_status: 'Employed',
  dti:               22.5,
  is_homeowner:      false,
  listing_category:  'Debt Consolidation',
  credit_score:      695,
  submitted_at:      '2025-04-20T09:30:00',
  reviewed_at:       null,
  admin_note:        null,
  default_probability: null,
  risk_level:        null,
  risk_score:        null,
  recommended_amount: null,
  recommended_term:   null,
}

export const MOCK_APPS = {
  PENDING_REVIEW: {
    ...base,
    status:              'PENDING_REVIEW',
    default_probability: 0.18,
    risk_level:          'LOW',
    risk_score:          18,
    recommended_amount:  14000,
    recommended_term:    36,
  },
  AUTO_REJECTED: {
    ...base,
    id:                  2,
    status:              'AUTO_REJECTED',
    default_probability: 0.63,
    risk_level:          'HIGH',
    risk_score:          63,
    recommended_amount:  null,
    recommended_term:    null,
  },
  ADMIN_REJECTED: {
    ...base,
    id:                  3,
    status:              'ADMIN_REJECTED',
    default_probability: 0.29,
    risk_level:          'MEDIUM',
    risk_score:          29,
    reviewed_at:         '2025-04-21T14:00:00',
    admin_note:          'Hồ sơ cần bổ sung giấy tờ chứng minh thu nhập.',
  },
  AWAITING_INFO: {
    ...base,
    id:                  4,
    status:              'AWAITING_INFO',
    default_probability: 0.12,
    risk_level:          'LOW',
    risk_score:          12,
    recommended_amount:  13500,
    recommended_term:    36,
    reviewed_at:         '2025-04-22T10:15:00',
  },
  INFO_SUBMITTED: {
    ...base,
    id:                  5,
    status:              'INFO_SUBMITTED',
    default_probability: 0.12,
    risk_level:          'LOW',
    risk_score:          12,
    recommended_amount:  13500,
    recommended_term:    36,
    reviewed_at:         '2025-04-22T10:15:00',
  },
}

export const MOCK_PERSONAL_INFO_OUT = {
  id:             1,
  application_id: 4,
  user_id:        1,
  full_name:      'Nguyễn Văn Test',
  id_card_number: '012345678901',
  phone:          '0912345678',
  email:          'testcustomer@creditintel.dev',
  date_of_birth:  '1995-06-15',
  address:        'Số 1, Đường Lê Lợi, Phường Bến Nghé, Quận 1, TP. HCM',
  submitted_at:   '2025-04-23T11:00:00',
}

/* ─────────────────────────────────────────────────────
   ADMIN MOCK DATA
───────────────────────────────────────────────────── */

export const MOCK_ADMIN_TOKEN =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9' +
  '.eyJzdWIiOiI5OSIsImV4cCI6OTk5OTk5OTk5OSwicm9sZSI6ImFkbWluIn0' +
  '.mock_admin_signature'

export const MOCK_ADMIN_USER = {
  id:         99,
  email:      'admin@creditintel.dev',
  username:   'AdminCreditIntel',
  role:       'admin',
  created_at: '2025-01-01T00:00:00',
}

// List đơn vay cho admin (nhiều trạng thái, nhiều records)
const makeApp = (id, status, riskLevel, riskScore, prob, userId, email) => ({
  id,
  user_id:             userId,
  user_email:          email,
  user_username:       `User_${userId}`,
  monthly_income:      Math.round((4000 + id * 500) * 10) / 10,
  loan_amount:         5000 + id * 2000,
  term:                [12, 24, 36, 48, 60][id % 5],
  employment_status:   id % 2 === 0 ? 'Employed' : 'Self-Employed',
  dti:                 Math.round((15 + id * 3) * 10) / 10,
  is_homeowner:        id % 3 === 0,
  listing_category:    ['Debt Consolidation', 'Home Improvement', 'Business', 'Education'][id % 4],
  credit_score:        550 + id * 20,
  status,
  default_probability: prob,
  risk_level:          riskLevel,
  risk_score:          riskScore,
  recommended_amount:  riskLevel === 'HIGH' ? null : 5000 + id * 1500,
  recommended_term:    riskLevel === 'HIGH' ? null : 36,
  admin_note:          status === 'ADMIN_REJECTED' ? 'Hồ sơ chưa đủ điều kiện.' : null,
  submitted_at:        new Date(Date.now() - id * 86400000).toISOString(),
  reviewed_at:         ['ADMIN_REJECTED', 'AWAITING_INFO', 'INFO_SUBMITTED'].includes(status)
    ? new Date(Date.now() - id * 43200000).toISOString() : null,
  reviewed_by:         ['ADMIN_REJECTED', 'AWAITING_INFO', 'INFO_SUBMITTED'].includes(status)
    ? 'admin@creditintel.dev' : null,
})

export const INITIAL_MOCK_ADMIN_APPS = [
  makeApp(10, 'PENDING_REVIEW',  'LOW',    18, 0.18, 2, 'alice@example.com'),
  makeApp(11, 'PENDING_REVIEW',  'MEDIUM', 35, 0.35, 3, 'bob@example.com'),
  makeApp(12, 'PENDING_REVIEW',  'HIGH',   72, 0.72, 4, 'carol@example.com'),
  makeApp(13, 'AUTO_REJECTED',   'HIGH',   85, 0.85, 5, 'dave@example.com'),
  makeApp(14, 'AUTO_REJECTED',   'HIGH',   91, 0.91, 6, 'eve@example.com'),
  makeApp(15, 'ADMIN_REJECTED',  'MEDIUM', 42, 0.42, 7, 'frank@example.com'),
  makeApp(16, 'AWAITING_INFO',   'LOW',    12, 0.12, 8, 'grace@example.com'),
  makeApp(17, 'AWAITING_INFO',   'LOW',    22, 0.22, 9, 'henry@example.com'),
  makeApp(18, 'INFO_SUBMITTED',  'LOW',    15, 0.15, 10, 'ivy@example.com'),
  makeApp(19, 'INFO_SUBMITTED',  'MEDIUM', 38, 0.38, 11, 'jack@example.com'),
  makeApp(20, 'PENDING_REVIEW',  'LOW',    20, 0.20, 12, 'kate@example.com'),
  makeApp(21, 'PENDING_REVIEW',  'MEDIUM', 45, 0.45, 13, 'leo@example.com'),
  makeApp(22, 'AUTO_REJECTED',   'HIGH',   78, 0.78, 14, 'mia@example.com'),
  makeApp(23, 'ADMIN_REJECTED',  'MEDIUM', 51, 0.51, 15, 'noah@example.com'),
  makeApp(24, 'INFO_SUBMITTED',  'LOW',    19, 0.19, 16, 'olivia@example.com'),
]

const loadFromStorage = (key, defaultData) => {
  try {
    const saved = localStorage.getItem(key)
    if (saved) return JSON.parse(saved)
  } catch (e) {
    console.error('Error loading mock data from storage', e)
  }
  return defaultData
}

export const MOCK_ADMIN_APPS = loadFromStorage('MOCK_ADMIN_APPS', INITIAL_MOCK_ADMIN_APPS)

export const MOCK_DASHBOARD_SUMMARY = {
  total_today:          7,
  pending_review:       5,
  approved_today:       2,
  rejected_today:       3,
  auto_rejected_today:  2,
}

export const MOCK_RISK_DISTRIBUTION = [
  { risk_level: 'LOW',    count: 6 },
  { risk_level: 'MEDIUM', count: 5 },
  { risk_level: 'HIGH',   count: 4 },
]

export const INITIAL_PERSONAL_INFOS = [
  {
    id:             2,
    application_id: 18,
    user_id:        10,
    full_name:      'Nguyễn Thị Ivy',
    id_card_number: '098765432101',
    phone:          '0987654321',
    email:          'ivy@example.com',
    date_of_birth:  '1992-03-20',
    address:        'Số 5, Đường Nguyễn Huệ, Phường Bến Nghé, Quận 1, TP. HCM',
    submitted_at:   '2025-04-22T15:30:00',
  }
]

export const MOCK_PERSONAL_INFOS = loadFromStorage('MOCK_PERSONAL_INFOS', INITIAL_PERSONAL_INFOS)

export const MOCK_CHAT_RESPONSES = [
  'Dựa trên thông tin hồ sơ của bạn, điểm tín dụng 695 được xếp vào nhóm "Khá". Để tăng điểm, bạn có thể: (1) Thanh toán đúng hạn các khoản nợ hiện có, (2) Giảm tỷ lệ sử dụng hạn mức thẻ tín dụng xuống dưới 30%, (3) Tránh mở nhiều tài khoản tín dụng mới trong thời gian ngắn.',
  'Tỷ lệ DTI (Debt-to-Income) là tổng các khoản thanh toán nợ hàng tháng chia cho thu nhập hàng tháng. DTI của bạn đang là 22.5% — ở mức tốt (dưới 36%). DTI cao sẽ làm giảm khả năng được duyệt vay.',
  'Với thu nhập $6,500/tháng và DTI 22.5%, hạn mức vay hợp lý là 3–5 lần thu nhập hàng tháng, tức khoảng $19,500–$32,500. Tuy nhiên, hệ thống AI đề xuất $13,500 để đảm bảo an toàn tài chính.',
  'Rất tiếc, tôi chưa có đủ thông tin để trả lời câu hỏi này. Vui lòng liên hệ bộ phận hỗ trợ hoặc thử hỏi lại với nội dung cụ thể hơn.',
]

let chatResponseIndex = 0
export const getNextChatResponse = () => {
  const r = MOCK_CHAT_RESPONSES[chatResponseIndex % MOCK_CHAT_RESPONSES.length]
  chatResponseIndex++
  return r
}
