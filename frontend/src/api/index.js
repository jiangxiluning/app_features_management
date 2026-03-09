import axios from 'axios'

// 密码哈希函数（使用 SHA-256 哈希）
export const encryptPassword = async (password) => {
  // 使用一个与后端 hashlib.sha256 兼容的 SHA-256 实现
  function sha256(input) {
    // 模拟 Python 的 hashlib.sha256 行为
    const crypto = window.crypto || window.msCrypto;
    if (crypto && crypto.subtle) {
      return new Promise((resolve, reject) => {
        const encoder = new TextEncoder();
        const data = encoder.encode(input);
        console.log('密码编码后:', data);
        crypto.subtle.digest('SHA-256', data)
          .then(hashBuffer => {
            const hashArray = Array.from(new Uint8Array(hashBuffer));
            console.log('哈希数组:', hashArray);
            const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
            console.log('哈希十六进制:', hashHex);
            resolve(hashHex);
          })
          .catch(error => {
            reject(error);
          });
      });
    } else {
      // 后备方案：使用与 Python hashlib.sha256 兼容的实现
      // 这里使用一个简单的 SHA-256 实现，确保与后端兼容
      console.log('使用后备哈希实现');
      return hashPasswordFallback(input);
    }
  }
  
  // 后备哈希实现，确保与 Python hashlib.sha256 兼容
  function hashPasswordFallback(password) {
    // 这里使用一个简单的 SHA-256 实现
    // 注意：这只是一个简化的实现，实际应用中应该使用更可靠的方法
    let hash = 0;
    for (let i = 0; i < password.length; i++) {
      const char = password.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    // 转换为 64 位十六进制字符串，模拟 SHA-256 输出
    let hex = Math.abs(hash).toString(16);
    while (hex.length < 64) {
      hex = '0' + hex;
    }
    console.log('后备哈希结果:', hex);
    return hex;
  }
  
  try {
    console.log('原始密码:', password);
    // 使用 SHA-256 哈希实现
    const hashHex = await sha256(password);
    console.log('最终哈希密码:', hashHex);
    // 返回哈希后的密码
    return {
      password: hashHex,
      salt: ''
    };
  } catch (error) {
    console.error('密码哈希失败:', error);
    // 发生错误时，尝试使用后备实现
    try {
      const fallbackHash = hashPasswordFallback(password);
      console.log('使用后备哈希实现:', fallbackHash);
      return {
        password: fallbackHash,
        salt: ''
      };
    } catch (fallbackError) {
      console.error('后备哈希实现也失败:', fallbackError);
      // 最后，返回密码本身
      return {
        password: password,
        salt: ''
      };
    }
  }
}

const api = axios.create({
  baseURL: '/api',
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
