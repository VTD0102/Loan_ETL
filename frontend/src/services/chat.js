import api from './api'

export const sendMessage     = (data)       => api.post('/chat', data)
export const getChatSessions = ()           => Promise.resolve({ data: [] }) // Endpoint đã bị loại bỏ ở kiến trúc Backend mới
