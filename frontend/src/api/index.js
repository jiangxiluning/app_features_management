import axios from 'axios'

// 密码哈希函数
export const encryptPassword = async (password) => {
  try {
    // 尝试使用 Web Crypto API 生成 SHA-256 哈希
    if (typeof crypto !== 'undefined' && crypto.subtle) {
      const encoder = new TextEncoder()
      const data = encoder.encode(password)
      const hashBuffer = await crypto.subtle.digest('SHA-256', data)
      const hashArray = Array.from(new Uint8Array(hashBuffer))
      const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('')
      // 返回哈希后的密码
      return {
        password: hashHex,
        salt: ''
      }
    } else {
      // 如果 Web Crypto API 不可用，使用简单的哈希方法
      let hash = 0
      for (let i = 0; i < password.length; i++) {
        const char = password.charCodeAt(i)
        hash = ((hash << 5) - hash) + char
        hash = hash & hash // 转换为 32 位整数
      }
      // 返回哈希后的密码
      return {
        password: hash.toString(16),
        salt: ''
      }
    }
  } catch (error) {
    console.error('密码哈希失败:', error)
    // 发生错误时，返回密码本身
    return {
      password: password,
      salt: ''
    }
  }
}

const api = axios.create({
  baseURL: 'http://127.0.0.1:5001/api',
  timeout: 10000
})

// 添加请求拦截器，确保携带token
api.interceptors.request.use(config => {
  console.log('发送请求:', config.url, config.data)
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 添加响应拦截器，查看响应结果
api.interceptors.response.use(response => {
  console.log('收到响应:', response.config.url, response.data)
  return response
}, error => {
  console.error('响应错误:', error.config?.url, error.message, error.response?.data)
  return Promise.reject(error)
})

// 认证相关
export const authAPI = {
  login: async (data) => {
    // 哈希密码
    const hashedPassword = await encryptPassword(data.password)
    // 构建新的请求数据，只包含必要的字段
    const hashedData = {
      username: data.username,
      password: hashedPassword.password,
      salt: hashedPassword.salt
    }
    return api.post('/auth/login', hashedData)
  },
  changePassword: async (data) => {
    // 哈希原密码和新密码
    const hashedOldPassword = await encryptPassword(data.old_password)
    const hashedNewPassword = await encryptPassword(data.new_password)
    // 构建新的请求数据
    const hashedData = {
      ...data,
      old_password: hashedOldPassword.password,
      old_salt: hashedOldPassword.salt,
      new_password: hashedNewPassword.password,
      new_salt: hashedNewPassword.salt
    }
    return api.post('/auth/change-password', hashedData)
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
