import assert from 'node:assert/strict'

import { formatCurrency, formatDate } from './format.js'

assert.equal(formatCurrency(15000000), '15.000.000 US$')
assert.equal(formatCurrency(null), 'Chưa có dữ liệu')
assert.equal(formatDate('2025-04-20T09:30:00'), '20/04/2025')
assert.equal(formatDate(undefined), 'Chưa có dữ liệu')
assert.equal(formatDate('not-a-date'), 'Chưa có dữ liệu')

console.log('format helpers ok')
