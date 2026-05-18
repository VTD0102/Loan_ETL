import api from './api'

export const sendMessage     = (data)       => api.post('/chat', data)
export const getChatHistory  = (sessionId)  => api.get('/chat/history', {
  params: sessionId ? { session_id: sessionId } : {},
})
