import assert from 'node:assert/strict'

import {
  buildLoanAdjustmentViewModel,
  normalizeLoanAdjustmentAction,
} from './loanAdjustment.js'

const pendingAction = {
  type: 'loan_term_adjustment',
  status: 'pending_confirmation',
  current_loan_amount: '12000',
  current_term: 12,
  expires_at: '2026-05-27T10:30:00.000Z',
  proposal: {
    loan_amount: '12000',
    term: 36,
    default_probability: 0.285,
    risk_level: 'LOW',
    risk_score: 28,
    adjustment_strategy: 'extend_term',
  },
  proposals: [
    {
      loan_amount: '12000',
      term: 36,
      default_probability: 0.285,
      risk_level: 'LOW',
      risk_score: 28,
      adjustment_strategy: 'extend_term',
    },
    {
      loan_amount: '9000',
      term: 60,
      default_probability: 0.31,
      risk_level: 'MEDIUM',
      risk_score: 31,
      adjustment_strategy: 'reduce_amount',
    },
    {
      loan_amount: '8000',
      term: 60,
      default_probability: 0.37,
      risk_level: 'MEDIUM',
      risk_score: 37,
      adjustment_strategy: 'reduce_amount',
    },
  ],
}

const normalized = normalizeLoanAdjustmentAction(pendingAction)
assert.equal(normalized.loanAmount, 12000)
assert.equal(normalized.term, 36)
assert.equal(normalized.defaultProbability, 0.285)
assert.equal(normalized.riskLevel, 'LOW')
assert.equal(normalized.expiresAt, '2026-05-27T10:30:00.000Z')

const viewModel = buildLoanAdjustmentViewModel(
  pendingAction,
  new Date('2026-05-27T10:10:00.000Z'),
)

assert.equal(viewModel.amountLabel, '12.000 US$')
assert.equal(viewModel.termLabel, '36 tháng')
assert.equal(viewModel.defaultProbabilityLabel, '28.5%')
assert.equal(viewModel.riskLabel, 'Thấp')
assert.equal(viewModel.expiresInLabel, 'Còn 20 phút')
assert.equal(viewModel.expired, false)
assert.equal(viewModel.options.length, 3)
assert.equal(viewModel.options[0].changeLabel, 'Tăng kỳ hạn từ 12 lên 36 tháng')
assert.equal(viewModel.options[1].amountLabel, '9.000 US$')
assert.equal(viewModel.options[1].termLabel, '60 tháng')
assert.equal(viewModel.options[1].defaultProbabilityLabel, '31.0%')
assert.equal(viewModel.options[1].changeLabel, 'Giảm số tiền vay từ 12.000 US$ còn 9.000 US$')

const expiredViewModel = buildLoanAdjustmentViewModel(
  pendingAction,
  new Date('2026-05-27T10:31:00.000Z'),
)
assert.equal(expiredViewModel.expiresInLabel, 'Đã hết hạn')
assert.equal(expiredViewModel.expired, true)

const legacyNaiveUtcExpiryViewModel = buildLoanAdjustmentViewModel(
  {
    ...pendingAction,
    expires_at: '2026-05-27T10:30:00.000',
  },
  new Date('2026-05-27T10:10:00.000Z'),
)
assert.equal(legacyNaiveUtcExpiryViewModel.expiresInLabel, 'Còn 20 phút')
assert.equal(legacyNaiveUtcExpiryViewModel.expired, false)

assert.equal(normalizeLoanAdjustmentAction(null), null)
assert.equal(normalizeLoanAdjustmentAction({ type: 'other' }), null)
assert.equal(normalizeLoanAdjustmentAction({
  ...pendingAction,
  proposal: { ...pendingAction.proposal, loan_amount: 'not-a-number' },
}), null)

console.log('loan adjustment helpers ok')
