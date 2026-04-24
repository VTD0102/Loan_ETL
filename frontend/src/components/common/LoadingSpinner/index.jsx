const LoadingSpinner = ({ size = 'md', className = '' }) => {
  const sizes = { sm: 'h-4 w-4', md: 'h-7 w-7', lg: 'h-10 w-10' }
  return (
    <span
      className={`inline-block animate-spin rounded-full border-2 border-gray-200 border-t-primary-600 ${sizes[size]} ${className}`}
      role="status"
      aria-label="Đang tải..."
    />
  )
}

export default LoadingSpinner
