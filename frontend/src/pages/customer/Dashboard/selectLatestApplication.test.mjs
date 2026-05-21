import assert from 'node:assert/strict'

import { selectLatestApplication } from './selectLatestApplication.js'

assert.equal(selectLatestApplication([]), null)
assert.equal(selectLatestApplication(null), null)
assert.equal(selectLatestApplication(undefined), null)

const latest = { id: 'new', submitted_at: '2025-04-22T10:15:00' }
const older = { id: 'old', submitted_at: '2025-04-20T09:30:00' }

assert.equal(selectLatestApplication([older, latest]), latest)
assert.equal(selectLatestApplication(latest), latest)

console.log('dashboard application selection ok')
