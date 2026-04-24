import { useNavigate } from 'react-router-dom'

const steps = [
  { icon: '📝', title: 'Nộp đơn vay', desc: 'Điền thông tin tài chính cơ bản trong vài phút. Không cần hồ sơ giấy tờ phức tạp.' },
  { icon: '🤖', title: 'AI đánh giá', desc: 'Mô hình AI phân tích hồ sơ, chấm điểm rủi ro và đề xuất hạn mức phù hợp theo thời gian thực.' },
  { icon: '✅', title: 'Kết quả nhanh', desc: 'Nhận phản hồi ngay lập tức. Admin phê duyệt cuối — minh bạch từng bước.' },
]

const features = [
  {
    icon: (
      <svg className="w-6 h-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
      </svg>
    ),
    title: 'Minh bạch tuyệt đối',
    desc: 'Mỗi quyết định đều có giải thích rõ ràng: tại sao được duyệt, tại sao bị từ chối, điểm rủi ro là bao nhiêu.',
  },
  {
    icon: (
      <svg className="w-6 h-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
    title: 'Xử lý tức thì',
    desc: 'Không cần chờ đợi hàng ngày. AI xử lý hồ sơ trong vài giây, kết quả sơ bộ ngay sau khi nộp.',
  },
  {
    icon: (
      <svg className="w-6 h-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
      </svg>
    ),
    title: 'AI-Powered',
    desc: 'Mô hình Random Forest được huấn luyện trên hơn 113,000 khoản vay thực. ROC-AUC 0.864.',
  },
  {
    icon: (
      <svg className="w-6 h-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    ),
    title: 'Trợ lý AI 24/7',
    desc: 'Chatbot RAG giải đáp mọi thắc mắc: điểm tín dụng, lãi suất, chiến lược cải thiện hồ sơ.',
  },
]

const LandingPage = () => {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-white">
      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-br from-white via-primary-50 to-white">
        <div className="absolute inset-0 opacity-[0.03]"
          style={{ backgroundImage: 'radial-gradient(circle at 1px 1px, #3b82f6 1px, transparent 0)', backgroundSize: '32px 32px' }} />
        <div className="relative max-w-6xl mx-auto px-4 sm:px-6 pt-24 pb-20 text-center">
          <div className="inline-flex items-center gap-2 bg-primary-50 border border-primary-100 text-primary-700 text-xs font-semibold px-4 py-1.5 rounded-full mb-6">
            <span className="w-2 h-2 bg-primary-500 rounded-full animate-pulse" />
            AI-Powered Credit Risk Analysis
          </div>
          <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold text-gray-900 leading-tight mb-6">
            Vay thông minh,<br />
            <span className="text-primary-600">quyết định nhanh</span>
          </h1>
          <p className="text-lg sm:text-xl text-gray-500 max-w-2xl mx-auto mb-10 leading-relaxed">
            CreditIntel sử dụng trí tuệ nhân tạo để đánh giá rủi ro tín dụng chính xác, minh bạch và tức thì — giúp bạn vay đúng số tiền, đúng thời điểm.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <button onClick={() => navigate('/register')} className="btn-primary text-base px-8 py-3 shadow-lg shadow-primary-200">
              Đăng ký ngay — miễn phí
            </button>
            <button onClick={() => navigate('/login')} className="btn-outline text-base px-8 py-3">
              Đăng nhập
            </button>
          </div>
          {/* Stats row */}
          <div className="mt-16 grid grid-cols-3 gap-6 max-w-lg mx-auto">
            {[['113K+', 'Khoản vay đã phân tích'], ['0.864', 'ROC-AUC Score'], ['< 3s', 'Thời gian phân tích']].map(([val, lbl]) => (
              <div key={lbl} className="text-center">
                <div className="text-2xl font-bold text-primary-600">{val}</div>
                <div className="text-xs text-gray-500 mt-1">{lbl}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-20 bg-white">
        <div className="max-w-5xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-14">
            <h2 className="text-3xl font-bold text-gray-900 mb-3">Quy trình 3 bước đơn giản</h2>
            <p className="text-gray-500">Từ nộp đơn đến kết quả — nhanh chóng và minh bạch</p>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            {steps.map((s, i) => (
              <div key={s.title} className="relative">
                {i < steps.length - 1 && (
                  <div className="hidden md:block absolute top-10 left-full w-full h-px border-t-2 border-dashed border-primary-100 -translate-x-1/2 z-0" />
                )}
                <div className="relative z-10 text-center p-6 rounded-2xl bg-white border border-gray-100 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300">
                  <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-primary-50 flex items-center justify-center text-3xl">
                    {s.icon}
                  </div>
                  <div className="absolute -top-3 -right-3 w-7 h-7 bg-primary-600 text-white text-xs font-bold rounded-full flex items-center justify-center shadow">
                    {i + 1}
                  </div>
                  <h3 className="font-bold text-gray-900 mb-2">{s.title}</h3>
                  <p className="text-sm text-gray-500 leading-relaxed">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 bg-gray-50">
        <div className="max-w-5xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-14">
            <h2 className="text-3xl font-bold text-gray-900 mb-3">Tại sao chọn CreditIntel?</h2>
            <p className="text-gray-500">Công nghệ AI giúp quá trình vay vốn trở nên công bằng và hiệu quả hơn</p>
          </div>
          <div className="grid sm:grid-cols-2 gap-6">
            {features.map((f) => (
              <div key={f.title} className="flex gap-4 p-6 bg-white rounded-2xl border border-gray-100 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex-shrink-0 w-12 h-12 bg-primary-50 rounded-xl flex items-center justify-center">
                  {f.icon}
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 mb-1">{f.title}</h3>
                  <p className="text-sm text-gray-500 leading-relaxed">{f.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 bg-primary-600">
        <div className="max-w-3xl mx-auto px-4 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">Bắt đầu ngay hôm nay</h2>
          <p className="text-primary-100 mb-8 text-lg">Đăng ký miễn phí, nhận kết quả trong vài giây. Không ràng buộc.</p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <button
              onClick={() => navigate('/register')}
              className="px-8 py-3 bg-white text-primary-700 font-semibold rounded-lg hover:bg-primary-50 transition-colors shadow-lg"
            >
              Đăng ký ngay
            </button>
            <button
              onClick={() => navigate('/login')}
              className="px-8 py-3 border-2 border-white text-white font-semibold rounded-lg hover:bg-primary-700 transition-colors"
            >
              Đăng nhập
            </button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 bg-white border-t border-gray-100 text-center text-sm text-gray-400">
        © {new Date().getFullYear()} CreditIntel. Powered by AI &amp; Machine Learning.
      </footer>
    </div>
  )
}

export default LandingPage
