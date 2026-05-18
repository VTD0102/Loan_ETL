/**
 * Admin API service
 * Tất cả admin API calls đặt ở đây — tái sử dụng axios instance chung từ api.js
 */
import api from './api'

/* ── Dashboard ─────────────────────────────────── */
export const getDashboardSummary     = ()       => api.get('/admin/dashboard/summary')
export const getRiskDistribution     = ()       => api.get('/admin/dashboard/risk-distribution')

/* ── Applications ───────────────────────────────── */
export const getPendingApplications  = (params) => api.get('/admin/applications/pending', { params })
export const getAllApplications       = (params) => api.get('/admin/applications', { params })
export const getAdminApplicationById = (id)     => api.get(`/admin/applications/${id}`)
export const getAdminApplicationCreditScore = (id) => api.get(`/credit-score/admin/applications/${id}`)
export const approveApplication      = (id, data) => api.post(`/admin/applications/${id}/approve`, data)
export const rejectApplication       = (id, data) => api.post(`/admin/applications/${id}/reject`, data)

/* ── Personal Info ──────────────────────────────── */
export const getPersonalInfo         = (id)     => api.get(`/admin/applications/${id}/personal-info`)
