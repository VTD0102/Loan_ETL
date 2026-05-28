import { useState, useRef, useEffect } from 'react'
import {
  getChatHistory,
  sendMessage,
  listChatSessions,
  createChatSession,
  deleteChatSession,
} from '../../../services/chat'
import ChatMessage from '../../../components/customer/ChatMessage'
import LoanAdjustmentActionCard from '../../../components/customer/LoanAdjustmentActionCard'
import LoadingSpinner from '../../../components/common/LoadingSpinner'

const SUGGESTIONS = [
  'Tại sao tôi bị đánh giá rủi ro cao?',
  'Làm thế nào để tăng điểm tín dụng?',
  'Tôi nên vay bao nhiêu là hợp lý?',
  'DTI là gì và ảnh hưởng như thế nào?',
  'Đề xuất gói vay phù hợp',
]

const CHAT_SESSION_KEY = 'creditintel_chat_session_id'
const DEFAULT_MESSAGE = {
  role: 'assistant',
  content: 'Xin chào! Tôi là trợ lý AI của CreditIntel. Tôi có thể giúp bạn hiểu về kết quả đánh giá tín dụng, cách cải thiện điểm tín dụng, hoặc tư vấn về khoản vay. Bạn cần hỏi gì?',
}

const TypingIndicator = () => (
  <div className="flex gap-3">
    <div className="relative w-8 h-8 flex-shrink-0">
      <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center text-xs font-semibold text-primary-600">
        AI
      </div>
      <span className="absolute inset-0 rounded-full border-2 border-primary-400 animate-ping opacity-60" />
    </div>
    <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm flex items-center gap-2">
      <span className="text-xs text-gray-400">Đang suy nghĩ</span>
      <span className="flex gap-1 ml-0.5">
        {[0, 1, 2].map((i) => (
          <span key={i} className="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.18}s` }} />
        ))}
      </span>
    </div>
  </div>
)

const SessionItem = ({ session, active, onClick, onDelete }) => {
  const [hover, setHover] = useState(false)
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      className={`group w-full text-left px-3 py-2 rounded-lg flex items-center gap-2 text-sm transition-colors
        ${active
          ? 'bg-primary-100 text-primary-900'
          : 'text-gray-700 hover:bg-gray-100'}`}
    >
      <svg className="w-4 h-4 flex-shrink-0 opacity-60" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.86 9.86 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
      <span className="flex-1 truncate">{session.title || 'Đoạn chat mới'}</span>
      {(hover || active) && (
        <span
          role="button"
          tabIndex={0}
          onClick={(e) => {
            e.stopPropagation()
            onDelete()
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              e.stopPropagation()
              onDelete()
            }
          }}
          className="opacity-60 hover:opacity-100 hover:text-red-600 transition-colors flex-shrink-0"
          title="Xóa đoạn chat"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M1 7h22M9 3h6a1 1 0 011 1v3H8V4a1 1 0 011-1z" />
          </svg>
        </span>
      )}
    </button>
  )
}

const ChatbotPage = () => {
  const [messages,     setMessages]     = useState([DEFAULT_MESSAGE])
  const [input,        setInput]        = useState('')
  const [loading,      setLoading]      = useState(false)
  const [sessionId,    setSessionId]    = useState(null)
  const [hydrating,    setHydrating]    = useState(true)
  const [typingMsgId,  setTypingMsgId]  = useState(null)
  const [sessions,     setSessions]     = useState([])
  const [sidebarOpen,  setSidebarOpen]  = useState(true)
  const [pendingAction, setPendingAction] = useState(null)
  const bottomRef = useRef(null)
  const inputRef  = useRef(null)

  const refreshSessions = async () => {
    try {
      const res = await listChatSessions()
      setSessions(res.data?.sessions || [])
    } catch {
      setSessions([])
    }
  }

  const loadSession = async (targetSessionId) => {
    setHydrating(true)
    try {
      const res = await getChatHistory(targetSessionId)
      const loaded = res.data?.messages || []
      const resolvedId = res.data?.session_id || targetSessionId || null
      setSessionId(resolvedId)
      setPendingAction(res.data?.pending_action || null)
      if (resolvedId) localStorage.setItem(CHAT_SESSION_KEY, resolvedId)
      else localStorage.removeItem(CHAT_SESSION_KEY)
      setMessages(loaded.length > 0
        ? loaded.map((msg) => ({ role: msg.role, content: msg.content, sources: msg.sources || [] }))
        : [DEFAULT_MESSAGE])
    } catch {
      setMessages([DEFAULT_MESSAGE])
      setSessionId(null)
      setPendingAction(null)
      localStorage.removeItem(CHAT_SESSION_KEY)
    } finally {
      setHydrating(false)
    }
  }

  // Initial hydration
  useEffect(() => {
    const init = async () => {
      const savedSessionId = localStorage.getItem(CHAT_SESSION_KEY)
      await refreshSessions()
      await loadSession(savedSessionId)
    }
    init()
  }, [])

  // Scroll to bottom on new message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleNewSession = async () => {
    if (loading) return
    try {
      const res = await createChatSession()
      const newId = res.data?.id
      if (!newId) return
      await refreshSessions()
      await loadSession(newId)
      inputRef.current?.focus()
    } catch {
      // ignore — toast could be added later
    }
  }

  const handleDeleteSession = async (targetId) => {
    if (!targetId) return
    if (!window.confirm('Xóa đoạn chat này? Hành động không thể hoàn tác.')) return
    try {
      await deleteChatSession(targetId)
      await refreshSessions()
      if (targetId === sessionId) {
        // current session was deleted — clear and start fresh
        localStorage.removeItem(CHAT_SESSION_KEY)
        setSessionId(null)
        setPendingAction(null)
        setMessages([DEFAULT_MESSAGE])
      }
    } catch {
      // ignore
    }
  }

  const handleSelectSession = (targetId) => {
    if (loading || targetId === sessionId) return
    loadSession(targetId)
  }

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
      const msgId = Date.now()
      setMessages((prev) => [...prev, { id: msgId, role: 'assistant', content: reply }])
      setPendingAction(res.data?.pending_action || null)
      setTypingMsgId(msgId)
      refreshSessions()
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
    <div className="h-full bg-gray-50 flex">
      {/* Sidebar */}
      <aside className={`${sidebarOpen ? 'w-64' : 'w-0'} flex-shrink-0 transition-all duration-200 overflow-hidden bg-white border-r border-gray-200 flex flex-col`}>
        <div className="px-3 py-3 border-b border-gray-200">
          <button
            onClick={handleNewSession}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium
              hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Đoạn chat mới
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1">
          {sessions.length === 0 ? (
            <p className="text-xs text-gray-400 px-3 py-2">Chưa có đoạn chat nào</p>
          ) : (
            sessions.map((s) => (
              <SessionItem
                key={s.id}
                session={s}
                active={s.id === sessionId}
                onClick={() => handleSelectSession(s.id)}
                onDelete={() => handleDeleteSession(s.id)}
              />
            ))
          )}
        </div>
      </aside>

      {/* Main column */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 px-4 py-4">
          <div className="max-w-3xl mx-auto flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen((v) => !v)}
              className="w-9 h-9 rounded-lg text-gray-600 hover:bg-gray-100 flex items-center justify-center transition-colors"
              title={sidebarOpen ? 'Ẩn danh sách chat' : 'Hiện danh sách chat'}
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
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
              <ChatMessage key={msg.id || i} message={msg} typewriter={!!msg.id && msg.id === typingMsgId} />
            ))}
            {loading && <TypingIndicator />}
            {pendingAction && (
              <div className="pl-11">
                <LoanAdjustmentActionCard
                  action={pendingAction}
                  loading={loading}
                  onConfirm={(index) => handleSend(`Xác nhận phương án ${index + 1}`)}
                  onCancel={() => handleSend('Hủy')}
                />
              </div>
            )}
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
    </div>
  )
}

export default ChatbotPage
