import { useState, useRef, useEffect } from 'react'
import { getChatHistory, sendMessage } from '../../../services/chat'
import ChatMessage from '../../../components/customer/ChatMessage'
import LoadingSpinner from '../../../components/common/LoadingSpinner'

const SUGGESTIONS = [
  'Tại sao tôi bị đánh giá rủi ro cao?',
  'Làm thế nào để tăng điểm tín dụng?',
  'Tôi nên vay bao nhiêu là hợp lý?',
  'DTI là gì và ảnh hưởng như thế nào?',
]

const CHAT_SESSION_KEY = 'creditintel_chat_session_id'
const DEFAULT_MESSAGE = {
  role: 'assistant',
  content: 'Xin chào! Tôi là trợ lý AI của CreditIntel. Tôi có thể giúp bạn hiểu về kết quả đánh giá tín dụng, cách cải thiện điểm tín dụng, hoặc tư vấn về khoản vay. Bạn cần hỏi gì?',
}

const TypingIndicator = () => (
  <div className="flex gap-3">
    <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center text-xs font-semibold text-gray-600 flex-shrink-0">
      AI
    </div>
    <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm flex items-center gap-1.5">
      {[0, 1, 2].map((i) => (
        <span key={i} className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
      ))}
    </div>
  </div>
)

const ChatbotPage = () => {
  const [messages,  setMessages]  = useState([DEFAULT_MESSAGE])
  const [input,     setInput]     = useState('')
  const [loading,   setLoading]   = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [hydrating, setHydrating] = useState(true)
  const bottomRef = useRef(null)
  const inputRef  = useRef(null)

  useEffect(() => {
    let cancelled = false
    const loadHistory = async () => {
      const savedSessionId = localStorage.getItem(CHAT_SESSION_KEY)
      try {
        const res = await getChatHistory(savedSessionId)
        if (cancelled) return
        const loaded = res.data?.messages || []
        if (res.data?.session_id) {
          setSessionId(res.data.session_id)
          localStorage.setItem(CHAT_SESSION_KEY, res.data.session_id)
        }
        if (loaded.length > 0) {
          setMessages(loaded.map((msg) => ({
            role: msg.role,
            content: msg.content,
            sources: msg.sources || [],
          })))
        }
      } catch {
        localStorage.removeItem(CHAT_SESSION_KEY)
      } finally {
        if (!cancelled) setHydrating(false)
      }
    }
    loadHistory()
    return () => { cancelled = true }
  }, [])

  // Scroll to bottom on new message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSend = async (text) => {
    const content = (text || input).trim()
    if (!content || loading || hydrating) return

    const userMsg = { role: 'user', content }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const res = await sendMessage({ message: content, session_id: sessionId })
      if (res.data?.session_id) {
        setSessionId(res.data.session_id)
        localStorage.setItem(CHAT_SESSION_KEY, res.data.session_id)
      }
      const reply = res.data?.response || res.data?.reply || res.data?.message || res.data?.content || 'Xin lỗi, tôi chưa hiểu câu hỏi. Bạn có thể diễn đạt lại không?'
      setMessages((prev) => [...prev, { role: 'assistant', content: reply }])
    } catch {
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: 'Rất tiếc, tôi đang gặp sự cố kỹ thuật. Vui lòng thử lại sau ít phút.',
      }])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="h-full bg-gray-50 flex flex-col">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-4 py-4">
        <div className="max-w-3xl mx-auto flex items-center gap-3">
          <div className="w-10 h-10 bg-primary-600 rounded-full flex items-center justify-center">
            <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <div>
            <h1 className="font-semibold text-gray-900">Trợ lý AI CreditIntel</h1>
            <div className="flex items-center gap-1.5 text-xs text-success-600">
              <span className="w-1.5 h-1.5 bg-success-500 rounded-full" />
              Online — Powered by RAG
            </div>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-6 space-y-5">
          {hydrating && (
            <div className="flex justify-center py-3">
              <LoadingSpinner size="sm" />
            </div>
          )}
          {messages.map((msg, i) => (
            <ChatMessage key={i} message={msg} />
          ))}
          {loading && <TypingIndicator />}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Suggestions — show only before first user message */}
      {messages.length === 1 && !hydrating && (
        <div className="max-w-3xl mx-auto px-4 pb-4 w-full">
          <p className="text-xs text-gray-400 mb-2 text-center">Gợi ý câu hỏi</p>
          <div className="flex flex-wrap gap-2 justify-center">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => handleSend(s)}
                className="text-xs px-3 py-1.5 bg-white border border-gray-200 rounded-full text-gray-600 hover:border-primary-400 hover:text-primary-600 hover:bg-primary-50 transition-colors shadow-sm"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="bg-white border-t border-gray-200 px-4 py-4">
        <div className="max-w-3xl mx-auto">
          <div className="flex items-end gap-3 bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 focus-within:border-primary-400 focus-within:ring-2 focus-within:ring-primary-100 transition-all">
            <textarea
              ref={inputRef}
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Nhập câu hỏi... (Enter để gửi)"
              disabled={hydrating}
              className="flex-1 bg-transparent resize-none text-sm text-gray-800 placeholder-gray-400 outline-none max-h-32"
              style={{ overflowY: 'auto' }}
            />
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || loading || hydrating}
              className="flex-shrink-0 w-9 h-9 bg-primary-600 text-white rounded-xl flex items-center justify-center
                         hover:bg-primary-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {loading
                ? <LoadingSpinner size="sm" />
                : (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                )}
            </button>
          </div>
          <p className="text-center text-xs text-gray-400 mt-2">Shift+Enter để xuống dòng</p>
        </div>
      </div>
    </div>
  )
}

export default ChatbotPage
