import { useEffect, useState, Children } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import Modal from '../../common/Modal'
import LoadingSpinner from '../../common/LoadingSpinner'
import { buildLoanAdjustmentViewModel } from '../LoanAdjustmentActionCard/loanAdjustment'

const percentLabel = (value) => `${((Number(value) || 0) * 100).toFixed(1)}%`

// ── Inline decorators for RAG text ───────────────────────────────────────────
const SourceChip = ({ name }) => (
  <span className="inline-flex items-center gap-1 align-baseline mx-0.5 px-1.5 py-0.5 rounded-md
    bg-primary-50 text-primary-700 text-[10px] font-medium border border-primary-100">
    <svg viewBox="0 0 24 24" className="w-2.5 h-2.5" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M14 2v6h6M9 13h6M9 17h6" />
    </svg>
    {name}
  </span>
)

const CurrencyBadge = ({ raw }) => (
  <span className="inline-block align-baseline mx-0.5 px-1.5 py-0.5 rounded
    bg-amber-50 text-amber-800 text-[10px] font-semibold border border-amber-100 tabular-nums">
    {raw}
  </span>
)

const STATUS_STYLES = {
  AUTO_REJECTED:   'bg-red-50 text-red-700 border-red-100',
  REJECTED:        'bg-red-50 text-red-700 border-red-100',
  ADMIN_REJECTED:  'bg-red-50 text-red-700 border-red-100',
  PENDING_REVIEW:  'bg-blue-50 text-blue-700 border-blue-100',
  AWAITING_INFO:   'bg-amber-50 text-amber-800 border-amber-100',
  APPROVED:        'bg-emerald-50 text-emerald-700 border-emerald-100',
  DRAFT:           'bg-gray-100 text-gray-700 border-gray-200',
}

const StatusBadge = ({ status }) => (
  <span className={`inline-block align-baseline mx-0.5 px-1.5 py-0.5 rounded
    text-[9px] font-semibold uppercase tracking-wide border ${STATUS_STYLES[status] || 'bg-gray-100 text-gray-700 border-gray-200'}`}>
    {status}
  </span>
)

const TEXT_PATTERNS = [
  {
    regex: /\[([\w.-]+\.md)\]/g,
    build: (match, key) => <SourceChip key={key} name={match[1]} />,
  },
  {
    regex: /\b(AUTO_REJECTED|ADMIN_REJECTED|REJECTED|PENDING_REVIEW|AWAITING_INFO|APPROVED|DRAFT)\b/g,
    build: (match, key) => <StatusBadge key={key} status={match[1]} />,
  },
  {
    regex: /(?:[$₫€£]\s?[\d,]+(?:\.\d+)?)/g,
    build: (match, key) => <CurrencyBadge key={key} raw={match[0]} />,
  },
]

const transformText = (text) => {
  if (!text || typeof text !== 'string') return text
  const matches = []
  TEXT_PATTERNS.forEach((p, patternIdx) => {
    let m
    p.regex.lastIndex = 0
    while ((m = p.regex.exec(text)) !== null) {
      matches.push({ start: m.index, end: m.index + m[0].length, match: m, patternIdx })
    }
  })
  if (matches.length === 0) return text
  matches.sort((a, b) => a.start - b.start)
  const filtered = []
  let cursor = 0
  for (const x of matches) {
    if (x.start >= cursor) {
      filtered.push(x)
      cursor = x.end
    }
  }
  const out = []
  let pos = 0
  filtered.forEach((x, i) => {
    if (x.start > pos) out.push(text.slice(pos, x.start))
    out.push(TEXT_PATTERNS[x.patternIdx].build(x.match, `tx-${i}`))
    pos = x.end
  })
  if (pos < text.length) out.push(text.slice(pos))
  return out
}

const wrapChildren = (children) => Children.map(children, (child) =>
  typeof child === 'string' ? transformText(child) : child
)

const markdownComponents = {
  p: ({ node, children, ...props }) => (
    <p className="mb-2 last:mb-0 leading-relaxed text-gray-700" {...props}>{wrapChildren(children)}</p>
  ),
  ul: ({ node, ...props }) => (
    <ul className="list-disc pl-5 space-y-1.5 mb-3 last:mb-0 marker:text-primary-500" {...props} />
  ),
  ol: ({ node, ...props }) => (
    <ol className="list-decimal pl-5 space-y-1.5 mb-3 last:mb-0 marker:text-primary-500" {...props} />
  ),
  li: ({ node, children, ...props }) => (
    <li className="leading-relaxed pl-0.5" {...props}>{wrapChildren(children)}</li>
  ),
  strong: ({ node, children, ...props }) => (
    <strong className="font-bold text-gray-900" {...props}>{wrapChildren(children)}</strong>
  ),
  em: ({ node, children, ...props }) => (
    <em className="italic text-gray-800" {...props}>{wrapChildren(children)}</em>
  ),
  h1: ({ node, ...props }) => <h4 className="text-sm font-bold text-primary-950 mt-4 mb-2 first:mt-0" {...props} />,
  h2: ({ node, ...props }) => <h4 className="text-sm font-bold text-primary-950 mt-3 mb-1.5 first:mt-0" {...props} />,
  h3: ({ node, ...props }) => <h5 className="text-xs font-bold text-gray-900 mt-2.5 mb-1" {...props} />,
}

const RejectedRagAdvisorModal = ({
  open,
  evaluation,
  pendingAction,
  ragResponse,
  submitting = false,
  submittedMessage = '',
  onClose,
  onConfirm,
  onCancel,
}) => {
  const model = buildLoanAdjustmentViewModel(pendingAction)
  const [selectedIndex, setSelectedIndex] = useState(0)

  useEffect(() => {
    setSelectedIndex(0)
  }, [pendingAction])

  const options = model?.options || []
  const selectedOption = options[selectedIndex] || options[0]
  const probability = Number(evaluation?.default_probability || 0)
  const dti = Number(evaluation?.computed_dti || 0)
  const probabilityPercent = Math.min(100, Math.max(0, probability * 100))
  const dtiPercent = Math.min(100, Math.max(0, dti * 100))
  const canSubmit = Boolean(selectedOption) && !model?.expired && !submitting && !submittedMessage

  return (
    <Modal open={open} onClose={onClose} title="AI đánh giá hồ sơ" maxWidth="max-w-5xl">
      <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
        <aside className="rounded-lg border border-gray-200 bg-gray-50 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-gray-950">Rủi ro hiện tại</p>
              <p className="mt-0.5 text-xs text-gray-500">Ngưỡng tự động từ chối: 40%</p>
            </div>
            <span className="rounded-full border border-danger-200 bg-danger-50 px-2.5 py-1 text-xs font-semibold text-danger-700">
              AUTO_REJECTED
            </span>
          </div>

          <div className="mt-5 flex justify-center">
            <div
              className="flex h-40 w-40 items-center justify-center rounded-full"
              style={{ background: `conic-gradient(#ef4444 0 ${probabilityPercent}%, #e5e7eb ${probabilityPercent}% 100%)` }}
            >
              <div className="flex h-28 w-28 flex-col items-center justify-center rounded-full bg-white shadow-inner">
                <span className="text-3xl font-bold text-gray-950">{percentLabel(probability)}</span>
                <span className="text-xs font-medium text-gray-500">P(default)</span>
              </div>
            </div>
          </div>

          <div className="mt-5 space-y-3">
            <div>
              <div className="mb-1.5 flex items-center justify-between text-xs">
                <span className="font-medium text-gray-500">Tỷ lệ nợ/thu nhập (DTI)</span>
                <span className="font-bold text-danger-600">{percentLabel(dti)}</span>
              </div>
              <div className="h-2 rounded-full bg-danger-100">
                <div className="h-2 rounded-full bg-danger-500" style={{ width: `${dtiPercent}%` }} />
              </div>
            </div>

            <div className="rounded-lg border border-gray-200 bg-white p-3 text-xs leading-5 text-gray-600">
              RAG giữ nguyên hồ sơ gốc và chỉ mô phỏng lại <strong>số tiền vay</strong> cùng <strong>kỳ hạn</strong>.
              Thu nhập, CIC, thông tin cá nhân và mục đích vay không bị sửa.
            </div>
          </div>
        </aside>

        <section className="min-w-0">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h3 className="text-base font-semibold text-gray-950">
                {options.length === 1 && selectedOption?.defaultProbability > 0.4
                  ? 'Phương án tối ưu (cần duyệt thủ công)'
                  : '3 khoản vay phù hợp'}
              </h3>
              <p className="mt-1 text-sm text-gray-500">
                {options.length === 1 && selectedOption?.defaultProbability > 0.4
                  ? 'Không tìm thấy gói vay nào tự động duyệt. Đây là phương án tốt nhất hiện tại.'
                  : 'Chọn một phương án. Khi bạn đồng ý, RAG sẽ nộp lại hồ sơ mới từ đơn bị từ chối.'}
              </p>
            </div>
            {model && (
              <span className={`w-fit rounded-full border px-2.5 py-1 text-xs font-semibold ${model.expired ? 'border-danger-200 bg-danger-50 text-danger-700' : 'border-primary-200 bg-primary-50 text-primary-700'}`}>
                {model.expiresInLabel}
              </span>
            )}
          </div>

          {submittedMessage ? (
            <div className="mt-5 rounded-lg border border-success-200 bg-success-50 p-5">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-success-600 text-white">
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <div>
                  <p className="font-semibold text-success-800">Đã gửi hồ sơ nộp lại</p>
                  <p className="mt-1 text-sm leading-6 text-success-700">{submittedMessage}</p>
                </div>
              </div>
            </div>
          ) : (
            <>
              {ragResponse && (
                <div className="mt-4 rounded-xl border border-primary-100 bg-gradient-to-br from-primary-50/50 to-blue-50/50 p-4 shadow-sm">
                  <div className="flex items-center gap-2 mb-3 pb-2 border-b border-primary-100/50">
                    <div className="flex h-5 w-5 items-center justify-center rounded bg-primary-100 text-primary-700">
                      <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 21l8.982-11.795H14.19l.818-5L6 16l3.813-.096z" />
                      </svg>
                    </div>
                    <span className="text-[11px] font-bold uppercase tracking-wider text-primary-700">Trợ lý AI tư vấn tài chính</span>
                  </div>
                  <div className="prose prose-sm max-w-none text-xs leading-relaxed text-gray-700">
                    <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                      {ragResponse}
                    </ReactMarkdown>
                  </div>
                </div>
              )}

              {options.length === 0 ? (
                <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                  Chưa có phương án nộp lại phù hợp. Vui lòng thử lại sau ít phút hoặc cải thiện hồ sơ trước khi nộp lại.
                </div>
              ) : (
                <div className="mt-4 grid gap-3 md:grid-cols-3">
                  {options.map((option, index) => {
                    const selected = index === selectedIndex
                    return (
                      <button
                        key={option.id}
                        type="button"
                        onClick={() => setSelectedIndex(index)}
                        disabled={submitting}
                        className={`rounded-lg border p-4 text-left transition-all ${
                          selected
                            ? 'border-primary-500 bg-primary-50 shadow-lg shadow-primary-100 ring-2 ring-primary-100'
                            : 'border-gray-200 bg-white hover:border-primary-200 hover:bg-primary-50/40'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-sm font-semibold text-gray-950">Phương án {option.optionNumber}</p>
                          <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${option.riskClassName}`}>
                            {option.riskLabel}
                          </span>
                        </div>
                        <p className="mt-4 text-2xl font-bold text-gray-950">{option.amountLabel}</p>
                        <p className="mt-1 text-sm text-gray-500">{option.termLabel}</p>
                        <div className="my-4 h-px bg-gray-200" />
                        <p className="text-xs font-medium uppercase text-gray-400">Xác suất vỡ nợ</p>
                        <p className="mt-1 text-base font-bold text-primary-700">{option.defaultProbabilityLabel}</p>
                      </button>
                    )
                  })}
                </div>
              )}

              {selectedOption && selectedOption.defaultProbability > 0.4 && (
                <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 flex items-start gap-2">
                  <svg className="w-5 h-5 flex-shrink-0 text-amber-600 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <div>
                    <span className="font-bold">Cảnh báo rủi ro:</span> Phương án đề xuất này có xác suất vỡ nợ là <span className="font-bold text-red-600">{percentLabel(selectedOption.defaultProbability)}</span> (vượt ngưỡng tự động duyệt 40.0%). Hồ sơ sẽ cần quản trị viên duyệt thủ công nếu khách hàng quyết định nộp lại.
                  </div>
                </div>
              )}
            </>
          )}

          <div className="mt-5 flex flex-col gap-2 sm:flex-row">
            <button type="button" onClick={onCancel || onClose} disabled={submitting} className="btn-outline flex-1">
              {submittedMessage ? 'Đóng' : 'Hủy'}
            </button>
            {!submittedMessage && (
              <button
                type="button"
                onClick={() => onConfirm?.(selectedIndex)}
                disabled={!canSubmit}
                className="btn-primary flex-[2]"
              >
                {submitting && <LoadingSpinner size="sm" className="mr-2" />}
                {submitting
                  ? 'Đang nộp lại...'
                  : selectedOption
                    ? `Đồng ý nộp lại phương án ${selectedOption.optionNumber}`
                    : 'Chưa có phương án phù hợp'}
              </button>
            )}
          </div>
        </section>
      </div>
    </Modal>
  )
}

export default RejectedRagAdvisorModal

