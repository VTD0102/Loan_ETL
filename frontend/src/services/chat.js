import api from './api'

export const sendMessage     = (data)       => api.post('/chat', data)
export const getChatHistory  = (sessionId)  => api.get('/chat/history', {
  params: sessionId ? { session_id: sessionId } : {},
})

export const listChatSessions   = ()          => api.get('/chat/sessions')
export const createChatSession  = ()          => api.post('/chat/sessions')
export const deleteChatSession  = (sessionId) => api.delete(`/chat/sessions/${sessionId}`)
