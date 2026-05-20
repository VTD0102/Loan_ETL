/**
 * CIC API service — Credit Information Center
 */
import api from './api'

/* Customer xem CIC của mình */
export const getMyCIC = () => api.get('/cic/me')

/* Admin tra cứu CIC theo CCCD */
export const lookupCIC = (cccd) => api.get(`/cic/lookup/${cccd}`)
