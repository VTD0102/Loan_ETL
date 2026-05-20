import { formatDateTime } from '../../../utils/format'

const STEPS = [
  { key: 'submitted',  label: 'Đã nộp đơn',          desc: 'Hồ sơ đã được tiếp nhận' },
  { key: 'ai_review',  label: 'AI phân tích',         desc: 'Hệ thống AI đánh giá rủi ro' },
  { key: 'admin',      label: 'Admin xét duyệt',      desc: 'Chuyên viên kiểm tra hồ sơ' },
  { key: 'info',       label: 'Thu thập thông tin',   desc: 'Xác minh thông tin ngân hàng' },
  { key: 'disburse',   label: 'Giải ngân',            desc: 'Chuyển tiền vào tài khoản' },
  { key: 'complete',   label: 'Hoàn tất',             desc: 'Hợp đồng đã có hiệu lực' },
]

const STATUS_STEP_MAP = {
  AUTO_REJECTED:  2,
  ADMIN_REJECTED: 3,
  PENDING_REVIEW: 2,
  AWAITING_INFO:  3,
  INFO_SUBMITTED: 4,
  DISBURSED:      6,   // all steps done
}

const ApplicationTimeline = ({ app }) => {
  const currentStep = STATUS_STEP_MAP[app.status] ?? 1

  return (
    <div className="py-2">
      <div className="relative">
        {/* Connector line */}
        <div className="absolute left-4 top-4 bottom-4 w-0.5 bg-gray-100" />

        <div className="space-y-5">
          {STEPS.map((step, idx) => {
            const done    = idx < currentStep
            const active  = idx === currentStep
            const failed  = active && (app.status === 'AUTO_REJECTED' || app.status === 'ADMIN_REJECTED')

            return (
              <div key={step.key} className="relative flex items-start gap-4 pl-0">
                {/* Dot */}
                <div className={`relative z-10 flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center border-2 transition-colors
                  ${done  ? 'bg-success-500 border-success-500'
                  : failed ? 'bg-danger-500 border-danger-500'
                  : active ? 'bg-white border-primary-500'
                  : 'bg-white border-gray-200'}`}
                >
                  {done ? (
                    <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : failed ? (
                    <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  ) : active ? (
                    <span className="w-2.5 h-2.5 rounded-full bg-primary-500 animate-pulse" />
                  ) : (
                    <span className="w-2 h-2 rounded-full bg-gray-200" />
                  )}
                </div>

                <div className="pb-1 min-w-0">
                  <p className={`text-sm font-semibold ${
                    done    ? 'text-success-700'
                    : failed  ? 'text-danger-700'
                    : active  ? 'text-primary-700'
                    : 'text-gray-400'}`}
                  >
                    {step.label}
                  </p>
                  <p className={`text-xs mt-0.5 ${done || active ? 'text-gray-500' : 'text-gray-300'}`}>
                    {step.desc}
                  </p>
                  {done && idx === 0 && app.submitted_at && (
                    <p className="text-xs text-gray-400 mt-0.5">{formatDateTime(app.submitted_at)}</p>
                  )}
                  {done && idx === 2 && app.reviewed_at && (
                    <p className="text-xs text-gray-400 mt-0.5">{formatDateTime(app.reviewed_at)}</p>
                  )}
                  {done && idx === 4 && app.disbursed_at && (
                    <p className="text-xs text-gray-400 mt-0.5">{formatDateTime(app.disbursed_at)}</p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default ApplicationTimeline
