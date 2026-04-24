import { useEffect, useState } from 'react'
import { getPendingApplications } from '../../../services/admin'
import ApplicationsTable from '../../../components/admin/ApplicationsTable'
import LoadingSpinner from '../../../components/common/LoadingSpinner'

const PAGE_LIMIT = 10

const PendingApplicationsPage = () => {
  const [items,   setItems]   = useState([])
  const [page,    setPage]    = useState(1)
  const [pages,   setPages]   = useState(1)
  const [total,   setTotal]   = useState(0)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  const fetchData = async (p = 1) => {
    setLoading(true)
    setError(null)
    try {
      const res = await getPendingApplications({ page: p, limit: PAGE_LIMIT })
      const d = res.data
      setItems(d.items || [])
      setPage(d.page  || p)
      setPages(d.pages || 1)
      setTotal(d.total || 0)
    } catch {
      setError('Không thể tải danh sách đơn chờ duyệt.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData(1) }, [])

  const handlePrev = () => { if (page > 1) fetchData(page - 1) }
  const handleNext = () => { if (page < pages) fetchData(page + 1) }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Đơn chờ xét duyệt</h1>
          <p className="text-gray-500 mt-1">
            {loading ? 'Đang tải...' : `${total} đơn đang chờ xem xét — sắp xếp theo ngày nộp (mới nhất trước)`}
          </p>
        </div>

        <div className="card p-6">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <LoadingSpinner size="lg" />
            </div>
          ) : error ? (
            <div className="text-center py-12 text-danger-600">
              <p className="mb-4">{error}</p>
              <button onClick={() => fetchData(page)} className="btn-primary">Thử lại</button>
            </div>
          ) : (
            <ApplicationsTable
              items={items}
              showStatus={false}
              page={page}
              pages={pages}
              onPrev={handlePrev}
              onNext={handleNext}
            />
          )}
        </div>
      </div>
    </div>
  )
}

export default PendingApplicationsPage
