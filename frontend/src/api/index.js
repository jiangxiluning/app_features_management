import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000
})

// 添加请求拦截器，确保携带token
api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 认证相关
export const authAPI = {
  login: (data) => api.post('/auth/login', data),
  changePassword: (data) => api.post('/auth/change-password', data)
}

// 功能相关
export const featureAPI = {
  getFeatures: (userRole, userId, options = {}) => api.get('/features', {
    params: {
      user_role: userRole,
      user_id: userId,
      ...options
    }
  }),
  createFeature: (data) => api.post('/features', data),
  updateFeature: (id, data) => api.put(`/features/${id}`, data),
  deleteFeature: (id, data) => api.delete(`/features/${id}`, { data }),
  moveFeature: (id, newParentId, data) => api.post(`/features/${id}/move`, { 
    new_parent_id: newParentId,
    ...data
  }),
  approveFeature: (id, data) => api.post(`/audit-logs/${id}/approve`, data),
  rejectFeature: (id, data) => api.post(`/audit-logs/${id}/reject`, data),
  withdrawAudit: (id, data) => api.post(`/audit-logs/${id}/withdraw`, data),
  getAuditLogs: (featureId) => api.get('/audit-logs', {
    params: {
      feature_id: featureId
    }
  })
}

// 统计相关
export const statisticsAPI = {
  getStatistics: () => api.get('/statistics')
}

// 应用版本管理相关
export const versionAPI = {
  getAppVersions: (appId) => api.get(`/app-versions/${appId}`),
  addAppVersion: (data) => api.post('/app-versions', data),
  deleteAppVersion: (id, data) => api.delete(`/app-versions/${id}`, { data })
}

// 设备管理相关
export const deviceAPI = {
  getDevices: () => api.get('/devices'),
  createDevice: (data) => api.post('/devices', data),
  updateDevice: (id, data) => api.put(`/devices/${id}`, data),
  deleteDevice: (id, data) => api.delete(`/devices/${id}`, { data })
}

export default api
