import { formatCurrency, RISK_META } from '../../../utils/format.js'

const PENDING_ACTION_TYPE = 'loan_term_adjustment'
const PENDING_ACTION_STATUS = 'pending_confirmation'
const EMPTY_LABEL = 'Chưa có dữ liệu'

const toFiniteNumber = (value) => {
  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? numberValue : null
}

const parseIsoTimestampMs = (value) => {
  if (!value || typeof value !== 'string') return Number.NaN
  const trimmed = value.trim()
  const hasTimezone = /(?:z|[+-]\d{2}:?\d{2})$/i.test(trimmed)
  return new Date(hasTimezone ? trimmed : `${trimmed}Z`).getTime()
}

const normalizeProposal = (proposal) => {
  if (!proposal || typeof proposal !== 'object') return null

  const loanAmount = toFiniteNumber(proposal.loan_amount)
  const term = toFiniteNumber(proposal.term)
  const defaultProbability = toFiniteNumber(proposal.default_probability)
  const riskScore = toFiniteNumber(proposal.risk_score)

  if (loanAmount === null || loanAmount <= 0) return null
  if (term === null || term <= 0) return null
  if (defaultProbability === null || defaultProbability < 0) return null

  return {
    loanAmount,
    term,
    defaultProbability,
    riskLevel: String(proposal.risk_level || '').toUpperCase(),
    riskScore,
    adjustmentStrategy: proposal.adjustment_strategy || null,
  }
}

const buildChangeLabel = (proposal, current) => {
  const currentAmount = current?.loanAmount
  const currentTerm = current?.term
  const strategy = proposal.adjustmentStrategy

  if (strategy === 'extend_term' || (currentTerm && proposal.term > currentTerm && proposal.loanAmount === currentAmount)) {
    return currentTerm
      ? `Tăng kỳ hạn từ ${currentTerm} lên ${proposal.term} tháng`
      : 'Tăng kỳ hạn trả nợ'
  }

  if (strategy === 'reduce_amount' || (currentAmount && proposal.loanAmount < currentAmount)) {
    return currentAmount
      ? `Giảm số tiền vay từ ${formatCurrency(currentAmount)} còn ${formatCurrency(proposal.loanAmount)}`
      : 'Giảm số tiền vay'
  }

  return 'Điều chỉnh khoản vay'
}

const buildProposalViewModel = (proposal, index = 0, current = null) => {
  const riskMeta = RISK_META[proposal.riskLevel]
  return {
    ...proposal,
    id: `proposal-${index + 1}`,
    optionNumber: index + 1,
    amountLabel: formatCurrency(proposal.loanAmount),
    termLabel: `${proposal.term} tháng`,
    defaultProbabilityLabel: `${(proposal.defaultProbability * 100).toFixed(1)}%`,
    riskLabel: riskMeta?.label || proposal.riskLevel || EMPTY_LABEL,
    riskClassName: riskMeta
      ? `${riskMeta.bg} ${riskMeta.text} ${riskMeta.border}`
      : 'bg-gray-50 text-gray-700 border-gray-200',
    changeLabel: buildChangeLabel(proposal, current),
  }
}

export const normalizeLoanAdjustmentAction = (action) => {
  if (!action || typeof action !== 'object') return null
  if (action.type !== PENDING_ACTION_TYPE) return null
  if (action.status !== PENDING_ACTION_STATUS) return null

  const primary = normalizeProposal(action.proposal)
  if (!primary) return null
  const currentLoanAmount = toFiniteNumber(action.current_loan_amount)
  const currentTerm = toFiniteNumber(action.current_term)
  const current = {
    loanAmount: currentLoanAmount,
    term: currentTerm,
  }
  const proposals = Array.isArray(action.proposals)
    ? action.proposals.map(normalizeProposal).filter(Boolean)
    : []
  const options = proposals.length > 0 ? proposals : [primary]

  return {
    sourceApplicationId: action.source_application_id || null,
    loanAmount: primary.loanAmount,
    term: primary.term,
    defaultProbability: primary.defaultProbability,
    riskLevel: primary.riskLevel,
    riskScore: primary.riskScore,
    adjustmentStrategy: primary.adjustmentStrategy,
    currentLoanAmount,
    currentTerm,
    expiresAt: action.expires_at || null,
    options,
    current,
  }
}

export const buildLoanAdjustmentViewModel = (action, now = new Date()) => {
  const normalized = normalizeLoanAdjustmentAction(action)
  if (!normalized) return null

  const expiresAtMs = parseIsoTimestampMs(normalized.expiresAt)
  const nowMs = now instanceof Date ? now.getTime() : new Date(now).getTime()
  const hasValidExpiry = Number.isFinite(expiresAtMs) && Number.isFinite(nowMs)
  const minutesRemaining = hasValidExpiry
    ? Math.ceil((expiresAtMs - nowMs) / 60000)
    : null
  const expired = minutesRemaining !== null && minutesRemaining <= 0
  const riskMeta = RISK_META[normalized.riskLevel]
  const current = {
    loanAmount: normalized.currentLoanAmount,
    term: normalized.currentTerm,
  }
  const options = normalized.options.map((proposal, index) =>
    buildProposalViewModel(proposal, index, current)
  )

  return {
    ...normalized,
    amountLabel: formatCurrency(normalized.loanAmount),
    termLabel: `${normalized.term} tháng`,
    defaultProbabilityLabel: `${(normalized.defaultProbability * 100).toFixed(1)}%`,
    riskLabel: riskMeta?.label || normalized.riskLevel || EMPTY_LABEL,
    riskClassName: riskMeta
      ? `${riskMeta.bg} ${riskMeta.text} ${riskMeta.border}`
      : 'bg-gray-50 text-gray-700 border-gray-200',
    changeLabel: buildChangeLabel(normalized, current),
    expiresInLabel: !hasValidExpiry
      ? EMPTY_LABEL
      : expired
        ? 'Đã hết hạn'
        : `Còn ${Math.max(1, minutesRemaining)} phút`,
    expired,
    options,
  }
}
