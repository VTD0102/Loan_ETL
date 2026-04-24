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
