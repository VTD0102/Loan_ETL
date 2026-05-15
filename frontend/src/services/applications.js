import api from './api'

export const evaluateApplication = (data)     => api.post('/applications/evaluate', data)
export const confirmApplication  = (data)     => api.post('/applications/confirm', data)
export const getMyApplication    = ()         => api.get('/applications/me')
export const getApplicationById  = (id)       => api.get(`/applications/${id}`)
export const submitPersonalInfo  = (id, data) => api.post(`/applications/${id}/personal-info`, data)
export const uploadDocuments     = (id, form) =>
  api.post(`/applications/${id}/documents`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
