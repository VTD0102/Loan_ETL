import { useState } from 'react'
import { toast } from 'react-toastify'
import Modal from '../../../components/common/Modal'
import LoadingSpinner from '../../../components/common/LoadingSpinner'
import { approveApplication, rejectApplication } from '../../../services/admin'

/**
 * ApproveRejectButtons — chỉ hiển thị khi status = PENDING_REVIEW
 * Props:
 *   appId      {number|string}  — application ID
 *   onSuccess  {function}       — callback sau khi approve/reject thành công
 */
const ApproveRejectButtons = ({ appId, onSuccess }) => {
  const [approveLoading, setApproveLoading] = useState(false)
  const [rejectLoading,  setRejectLoading]  = useState(false)
  const [confirmOpen,    setConfirmOpen]     = useState(false)
  const [rejectOpen,     setRejectOpen]      = useState(false)
  const [rejectReason,   setRejectReason]    = useState('')
  const [reasonError,    setReasonError]     = useState('')

  /* ── Approve ─────────────────────────────────────── */
  const handleApprove = async () => {
    setApproveLoading(true)
    try {
      await approveApplication(appId, {})
      toast.success('Đã duyệt đơn vay thành công!')
      setConfirmOpen(false)
      onSuccess?.()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Không thể duyệt đơn. Vui lòng thử lại.')
    } finally {
      setApproveLoading(false)
    }
  }

  /* ── Reject ──────────────────────────────────────── */
  const handleRejectSubmit = async () => {
    if (!rejectReason.trim()) {
      setReasonError('Vui lòng nhập lý do từ chối.')
      return
    }
    setRejectLoading(true)
    try {
      await rejectApplication(appId, { reason: rejectReason.trim() })
      toast.success('Đã từ chối đơn vay.')
      setRejectOpen(false)
      setRejectReason('')
      onSuccess?.()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Không thể từ chối. Vui lòng thử lại.')
    } finally {
      setRejectLoading(false)
    }
  }

  return (
    <>
      <div className="flex flex-wrap gap-3">
        {/* Approve button */}
        <button
          onClick={() => setConfirmOpen(true)}
          className="btn-primary flex items-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          Duyệt đơn
        </button>

        {/* Reject button */}
        <button
          onClick={() => { setRejectReason(''); setReasonError(''); setRejectOpen(true) }}
          className="btn-danger flex items-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
          Từ chối
        </button>
      </div>

      {/* ── Confirm Approve Modal ─────────────────────── */}
      <Modal open={confirmOpen} onClose={() => setConfirmOpen(false)} title="Xác nhận duyệt đơn">
        <p className="text-gray-600 mb-5">
          Bạn có chắc muốn <strong className="text-success-700">duyệt</strong> đơn vay này?
          Hệ thống sẽ chuyển trạng thái sang <strong>Chờ thông tin</strong> và thông báo đến khách hàng.
        </p>
        <div className="flex gap-3 justify-end">
          <button onClick={() => setConfirmOpen(false)} className="btn-outline">
            Hủy
          </button>
          <button onClick={handleApprove} disabled={approveLoading} className="btn-primary flex items-center gap-2">
            {approveLoading && <LoadingSpinner size="sm" />}
            {approveLoading ? 'Đang xử lý...' : 'Xác nhận duyệt'}
          </button>
        </div>
      </Modal>

      {/* ── Reject Modal ─────────────────────────────── */}
      <Modal open={rejectOpen} onClose={() => setRejectOpen(false)} title="Từ chối đơn vay" maxWidth="max-w-lg">
        <div className="space-y-4">
          <p className="text-gray-600">
            Vui lòng nhập lý do từ chối. Lý do này sẽ được gửi đến khách hàng.
          </p>
          <div>
            <label className="label">Lý do từ chối <span className="text-danger-500">*</span></label>
            <textarea
              className={`input resize-none ${reasonError ? 'input-error' : ''}`}
              rows={4}
              placeholder="Ví dụ: Hồ sơ chưa đủ điều kiện vay vốn do tỷ lệ DTI quá cao..."
              value={rejectReason}
              onChange={(e) => { setRejectReason(e.target.value); setReasonError('') }}
            />
            {reasonError && <p className="error-msg">{reasonError}</p>}
          </div>
          <div className="flex gap-3 justify-end pt-1">
            <button onClick={() => setRejectOpen(false)} className="btn-outline">
              Hủy
            </button>
            <button onClick={handleRejectSubmit} disabled={rejectLoading} className="btn-danger flex items-center gap-2">
              {rejectLoading && <LoadingSpinner size="sm" />}
              {rejectLoading ? 'Đang xử lý...' : 'Xác nhận từ chối'}
            </button>
          </div>
        </div>
      </Modal>
    </>
  )
}

export default ApproveRejectButtons
