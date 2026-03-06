import axios from 'axios'

// 密码加密函数
export const encryptPassword = async (password) => {
  // 使用 Web Crypto API 生成随机盐
  const salt = crypto.getRandomValues(new Uint8Array(16))
  // 生成密钥
  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(password),
    { name: 'PBKDF2' },
    false,
    ['deriveBits', 'deriveKey']
  )
  // 派生密钥
  const derivedKey = await crypto.subtle.deriveKey(
    {
      name: 'PBKDF2',
      salt: salt,
      iterations: 100000,
      hash: 'SHA-256'
    },
    key,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt']
  )
  // 生成随机初始化向量
  const iv = crypto.getRandomValues(new Uint8Array(12))
  // 加密密码
  const encrypted = await crypto.subtle.encrypt(
    {
      name: 'AES-GCM',
      iv: iv
    },
    derivedKey,
    new TextEncoder().encode(password)
  )
  // 返回加密后的密码、盐和初始化向量
  return {
    password: btoa(String.fromCharCode(...new Uint8Array(encrypted))),
    salt: btoa(String.fromCharCode(...salt)),
    iv: btoa(String.fromCharCode(...iv))
  }
}

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
  login: async (data) => {
    // 加密密码
    const encryptedPassword = await encryptPassword(data.password)
    // 构建新的请求数据
    const encryptedData = {
      ...data,
      password: encryptedPassword.password,
      salt: encryptedPassword.salt,
      iv: encryptedPassword.iv
    }
    return api.post('/auth/login', encryptedData)
  },
  changePassword: async (data) => {
    // 加密原密码和新密码
    const encryptedOldPassword = await encryptPassword(data.old_password)
    const encryptedNewPassword = await encryptPassword(data.new_password)
    // 构建新的请求数据
    const encryptedData = {
      ...data,
      old_password: encryptedOldPassword.password,
      old_salt: encryptedOldPassword.salt,
      old_iv: encryptedOldPassword.iv,
      new_password: encryptedNewPassword.password,
      new_salt: encryptedNewPassword.salt,
      new_iv: encryptedNewPassword.iv
    }
    return api.post('/auth/change-password', encryptedData)
  }
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
