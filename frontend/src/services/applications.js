import api from './api'

export const submitApplication  = (data)           => api.post('/applications', data)
export const getMyApplication   = ()               => api.get('/applications/me')
export const getApplicationById = (id)             => api.get(`/applications/${id}`)
export const submitPersonalInfo = (id, data)       => api.post(`/applications/${id}/personal-info`, data)
