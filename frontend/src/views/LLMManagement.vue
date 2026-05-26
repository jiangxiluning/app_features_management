<template>
  <div class="llm-management">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>大模型配置</h2>
        </div>
      </template>
      
      <el-form 
        ref="configFormRef"
        :model="configForm" 
        :rules="formRules"
        label-width="140px"
        class="config-form"
      >
        <el-divider content-position="left">基础配置</el-divider>
        
        <el-form-item label="配置名称" prop="name">
          <el-input v-model="configForm.name" placeholder="配置名称" />
        </el-form-item>
        
        <el-form-item label="Base URL" prop="base_url">
          <el-input v-model="configForm.base_url" placeholder="例如: https://api.openai.com/v1" />
        </el-form-item>
        
        <el-form-item label="API Key" prop="api_key">
          <el-input v-model="configForm.api_key" type="password" show-password placeholder="输入API Key" />
        </el-form-item>
        
        <el-form-item label="模型名称" prop="model_name">
          <el-input v-model="configForm.model_name" placeholder="例如: gpt-3.5-turbo" />
        </el-form-item>
        
        <el-form-item label="开启联网搜索">
          <el-switch v-model="configForm.enable_search" />
          <span style="margin-left: 10px; color: #909399; font-size: 12px;">
            启用后大模型可以访问网络信息（仅支持部分模型）
          </span>
        </el-form-item>
        
        <el-divider content-position="left">代理配置（可选）</el-divider>
        
        <el-form-item label="不使用代理">
          <el-switch v-model="configForm.no_proxy" />
          <span style="margin-left: 10px; color: #909399; font-size: 12px;">
            开启后大模型调用不使用任何代理
          </span>
        </el-form-item>
        
        <div v-show="!configForm.no_proxy">
          <el-form-item label="HTTP 和 HTTPS 代理一致">
            <el-switch v-model="configForm.same_proxy" />
            <span style="margin-left: 10px; color: #909399; font-size: 12px;">
              开启后 HTTPS 代理配置与 HTTP 代理保持一致
            </span>
          </el-form-item>
          
          <el-form-item label="HTTP Proxy">
            <el-input 
              v-model="configForm.http_proxy" 
              placeholder="例如: http://127.0.0.1:7890" 
              @input="syncHttpsProxy"
            />
          </el-form-item>
          
          <el-form-item label="HTTPS Proxy" v-if="!configForm.same_proxy">
            <el-input v-model="configForm.https_proxy" placeholder="例如: http://127.0.0.1:7890" />
          </el-form-item>
        </div>
        
        <el-divider content-position="left">Prompt 配置</el-divider>
        
        <el-form-item label="系统提示词">
          <el-input 
            v-model="configForm.system_prompt" 
            type="textarea" 
            :rows="4"
            placeholder="系统提示词，指导大模型的行为"
          />
          <div style="margin-top: 8px; color: #909399; font-size: 12px;" v-pre>
            可用占位符: {{app_name}}, {{app_description}}, {{feature_name}}, {{feature_description}}
          </div>
        </el-form-item>
        
        <el-form-item label="用户提示词">
          <el-input 
            v-model="configForm.user_prompt" 
            type="textarea" 
            :rows="6"
            placeholder="用户提示词，包含待优化的内容"
          />
          <div style="margin-top: 8px; color: #909399; font-size: 12px;" v-pre>
            可用占位符: {{app_name}}, {{app_description}}, {{feature_name}}, {{feature_description}}
          </div>
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" @click="saveConfig" :loading="saving">
            保存配置
          </el-button>
          <el-button @click="testConnection" :loading="testing">
            测试连接
          </el-button>
          <el-button @click="resetToDefault">
            恢复默认
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { llmAPI } from '../api'

const configFormRef = ref(null)
const saving = ref(false)
const testing = ref(false)

const defaultConfig = {
  name: 'default',
  base_url: 'https://api.openai.com/v1',
  api_key: '',
  model_name: 'gpt-3.5-turbo',
  enable_search: false,
  system_prompt: '你是一个专业的功能描述优化助手，帮助用户完善功能描述内容。',
  user_prompt: '请优化以下功能描述，使其更加清晰、专业、完整：\n应用名称：{{app_name}}\n应用描述：{{app_description}}\n功能名称：{{feature_name}}\n功能描述：{{feature_description}}',
  http_proxy: '',
  https_proxy: '',
  no_proxy: false,
  same_proxy: false
}

const configForm = reactive({
  name: '',
  base_url: '',
  api_key: '',
  model_name: '',
  enable_search: false,
  system_prompt: '',
  user_prompt: '',
  http_proxy: '',
  https_proxy: '',
  no_proxy: false,
  same_proxy: false
})

const syncHttpsProxy = () => {
  if (configForm.same_proxy) {
    configForm.https_proxy = configForm.http_proxy
  }
}

const formRules = {
  name: [
    { required: true, message: '请输入配置名称', trigger: 'blur' }
  ],
  base_url: [
    { required: true, message: '请输入Base URL', trigger: 'blur' }
  ],
  model_name: [
    { required: true, message: '请输入模型名称', trigger: 'blur' }
  ]
}

const loadConfig = async () => {
  try {
    const response = await llmAPI.getConfig()
    Object.assign(configForm, response.data)
  } catch (error) {
    if (error.response?.status !== 404) {
      ElMessage.error('加载配置失败: ' + (error.response?.data?.message || error.message))
    }
    // 如果没有配置，使用默认配置
    Object.assign(configForm, defaultConfig)
  }
}

const saveConfig = async () => {
  if (!configFormRef.value) return
  
  try {
    await configFormRef.value.validate()
  } catch (error) {
    return
  }
  
  saving.value = true
  try {
    await llmAPI.saveConfig(configForm)
    ElMessage.success('配置保存成功')
  } catch (error) {
    ElMessage.error('保存配置失败: ' + (error.response?.data?.message || error.message))
  } finally {
    saving.value = false
  }
}

const testConnection = async () => {
  if (!configForm.base_url || !configForm.api_key) {
    ElMessage.warning('请先配置Base URL和API Key')
    return
  }
  
  testing.value = true
  try {
    const response = await llmAPI.testConnection()
    if (response.data.success) {
      ElMessage.success(response.data.message || '连接成功')
    } else {
      ElMessage.error(response.data.message || '连接失败')
    }
  } catch (error) {
    ElMessage.error('连接测试失败: ' + (error.response?.data?.message || error.message))
  } finally {
    testing.value = false
  }
}

const resetToDefault = async () => {
  try {
    await ElMessageBox.confirm('确定要恢复默认配置吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    Object.assign(configForm, defaultConfig)
    ElMessage.success('已恢复默认配置')
  } catch (error) {
    // 用户取消
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.llm-management {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h2 {
  margin: 0;
  font-size: 20px;
  color: #303133;
}

.config-form {
  max-width: 800px;
  margin: 0 auto;
}
</style>