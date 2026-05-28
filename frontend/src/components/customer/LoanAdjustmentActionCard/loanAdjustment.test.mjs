import assert from 'node:assert/strict'

import {
  buildLoanAdjustmentViewModel,
  normalizeLoanAdjustmentAction,
} from './loanAdjustment.js'

const pendingAction = {
  type: 'loan_term_adjustment',
  status: 'pending_confirmation',
  expires_at: '2026-05-27T10:30:00.000Z',
  proposal: {
    loan_amount: '12000',
    term: 36,
    default_probability: 0.285,
    risk_level: 'LOW',
    risk_score: 28,
  },
  proposals: [
    {
      loan_amount: '12000',
      term: 36,
      default_probability: 0.285,
      risk_level: 'LOW',
      risk_score: 28,
    },
    {
      loan_amount: '10000',
      term: 24,
      default_probability: 0.31,
      risk_level: 'MEDIUM',
      risk_score: 31,
    },
    {
      loan_amount: '8000',
      term: 12,
      default_probability: 0.37,
      risk_level: 'MEDIUM',
      risk_score: 37,
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
assert.equal(viewModel.options[1].amountLabel, '10.000 US$')
assert.equal(viewModel.options[1].termLabel, '24 tháng')
assert.equal(viewModel.options[1].defaultProbabilityLabel, '31.0%')

const expiredViewModel = buildLoanAdjustmentViewModel(
  pendingAction,
  new Date('2026-05-27T10:31:00.000Z'),
)
assert.equal(expiredViewModel.expiresInLabel, 'Đã hết hạn')
assert.equal(expiredViewModel.expired, true)

assert.equal(normalizeLoanAdjustmentAction(null), null)
assert.equal(normalizeLoanAdjustmentAction({ type: 'other' }), null)
assert.equal(normalizeLoanAdjustmentAction({
  ...pendingAction,
  proposal: { ...pendingAction.proposal, loan_amount: 'not-a-number' },
}), null)

console.log('loan adjustment helpers ok')
