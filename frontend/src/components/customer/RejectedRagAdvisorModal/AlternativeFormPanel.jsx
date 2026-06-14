const AlternativeFormPanel = ({
  selectedOption,
  submitting = false,
  onCreateAlternative,
}) => {
  if (!selectedOption) return null

  return (
    <div className="mt-4 rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-gray-950">Nộp form khác</p>
          <p className="mt-1 text-sm leading-6 text-gray-600">
            Tạo bản nháp từ form {selectedOption.optionNumber} để chỉnh thêm số tiền hoặc kỳ hạn trước khi gửi lại.
          </p>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-gray-600">
            <span className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1">{selectedOption.amountLabel}</span>
            <span className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1">{selectedOption.termLabel}</span>
            <span className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1">{selectedOption.changeLabel}</span>
          </div>
        </div>
        <button
          type="button"
          onClick={onCreateAlternative}
          disabled={submitting}
          className="btn-outline shrink-0"
        >
          Chỉnh form khác
        </button>
      </div>
    </div>
  )
}

export default AlternativeFormPanel
