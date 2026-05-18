import { useEffect, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getAllApplications } from '../../../services/admin'
import ApplicationsTable from '../../../components/admin/ApplicationsTable'
import FilterBar from '../../../components/admin/FilterBar'
import LoadingSpinner from '../../../components/common/LoadingSpinner'

const PAGE_LIMIT = 10

const AllApplicationsPage = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  const [items,   setItems]   = useState([])
  const [page,    setPage]    = useState(1)
  const [pages,   setPages]   = useState(1)
  const [total,   setTotal]   = useState(0)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)
  const [filters, setFilters] = useState({})

  const filtersFromQuery = useCallback(() => ({
    status:     searchParams.get('status')     || '',
    risk_level: searchParams.get('risk_level') || '',
    from_date:  searchParams.get('from_date')  || '',
    to_date:    searchParams.get('to_date')    || '',
  }), [searchParams])

  const fetchData = useCallback(async (p = 1, f = {}) => {
    setLoading(true)
    setError(null)
    try {
      // Build clean params (exclude empty strings)
      const params = { page: p, limit: PAGE_LIMIT }
      if (f.status)     params.status     = f.status
      if (f.risk_level) params.risk_level = f.risk_level
      if (f.from_date)  params.from_date  = f.from_date
      if (f.to_date)    params.to_date    = f.to_date

      const res = await getAllApplications(params)
      const d   = res.data
      setItems(d.items || [])
      setPage(d.page   || p)
      setPages(d.pages || 1)
      setTotal(d.total || 0)
    } catch {
      setError('Không thể tải danh sách đơn vay.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const queryFilters = filtersFromQuery()
    setFilters(queryFilters)
    setPage(1)
    fetchData(1, queryFilters)
  }, [fetchData, filtersFromQuery])

  const updateQuery = (nextFilters) => {
    const clean = {}
    Object.entries(nextFilters).forEach(([key, value]) => {
      if (value) clean[key] = value
    })
    setSearchParams(clean)
  }

  const handleApplyFilters = (f) => {
    updateQuery(f)
  }

  const handleClearFilters = () => {
    setSearchParams({})
  }

  const handlePrev = () => { if (page > 1) fetchData(page - 1, filters) }
  const handleNext = () => { if (page < pages) fetchData(page + 1, filters) }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Tất cả đơn vay</h1>
          <p className="text-gray-500 mt-1">
            {loading ? 'Đang tải...' : `${total} đơn vay`}
          </p>
        </div>

        {/* Filter */}
        <FilterBar
          filters={filters}
          onApply={handleApplyFilters}
          onClear={handleClearFilters}
        />

        {/* Table */}
        <div className="card p-6">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <LoadingSpinner size="lg" />
            </div>
          ) : error ? (
            <div className="text-center py-12 text-danger-600">
              <p className="mb-4">{error}</p>
              <button onClick={() => fetchData(page, filters)} className="btn-primary">Thử lại</button>
            </div>
          ) : (
            <ApplicationsTable
              items={items}
              showStatus={true}
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

export default AllApplicationsPage
