export const selectLatestApplication = (data) => {
  if (!data) return null
  if (!Array.isArray(data)) return data
  if (data.length === 0) return null

  return [...data].sort((a, b) => {
    const aTime = new Date(a?.submitted_at || 0).getTime()
    const bTime = new Date(b?.submitted_at || 0).getTime()
    return bTime - aTime
  })[0] || null
}
