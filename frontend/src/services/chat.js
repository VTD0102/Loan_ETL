import api from './api'

export const sendMessage     = (data)       => api.post('/chat', data)
export const getChatSessions = ()           => api.get('/chat/sessions')
