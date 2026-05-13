import { mockHandlers } from './src/mocks/mockHandlers.js'

async function run() {
  const config = {
    method: 'get',
    url: '/admin/applications',
    params: { page: 1, limit: 10 }
  }
  try {
    const res = await mockHandlers(config)
    console.log("SUCCESS:", res)
  } catch (e) {
    console.error("ERROR:", e)
  }
}
run()
