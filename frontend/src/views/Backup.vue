<template>
  <div class="backup-container">
    <el-card class="mb-4">
      <div class="card-header">
        <h2>备份管理</h2>
        <el-button type="primary" @click="triggerBackup" :loading="triggerLoading">手动备份</el-button>
      </div>
    </el-card>

    <el-card class="mb-4">
      <template #header>
        <div class="card-header">
          <h3>备份配置</h3>
        </div>
      </template>
      <el-form :model="backupConfig" label-width="120px">
        <el-form-item label="备份间隔">
          <el-input v-model="backupIntervalText" disabled></el-input>
        </el-form-item>
        <el-form-item label="保留备份个数">
          <el-input v-model="backupConfig.keep_latest" disabled></el-input>
        </el-form-item>
        <el-form-item label="启用自动备份">
          <el-switch v-model="backupConfig.is_enabled" disabled></el-switch>
        </el-form-item>
        <el-form-item label="最后备份时间">
          <el-input v-model="lastBackupTime" disabled></el-input>
        </el-form-item>
        <el-form-item label="备份路径">
          <el-input v-model="backupPath" disabled></el-input>
        </el-form-item>
        <el-form-item>
          <el-button type="info" disabled>配置只能通过配置文件修改</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <template #header>
        <div class="card-header">
          <h3>备份历史</h3>
        </div>
      </template>
      <el-table :data="backupList" style="width: 100%">
        <el-table-column prop="filename" label="备份文件名" width="300"></el-table-column>
        <el-table-column prop="size" label="大小" width="120">
          <template #default="scope">
            {{ formatFileSize(scope.row.size) }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="200"></el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="scope">
            <el-button type="primary" size="small" @click="restoreBackup(scope.row.filename)" :loading="restoreLoading[scope.row.filename]">
              恢复
            </el-button>
            <el-button type="danger" size="small" @click="deleteBackup(scope.row.filename)" :loading="deleteLoading[scope.row.filename]">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="backupList.length === 0" class="empty-backup">
        <el-empty description="暂无备份记录"></el-empty>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

// 响应式数据
const backupConfig = ref({
  backup_interval: '1 week',
  keep_latest: 10,
  is_enabled: true
})
const lastBackupTime = ref('')
const backupPath = ref('./backups')
const backupList = ref([])
const triggerLoading = ref(false)
const restoreLoading = ref({})
const deleteLoading = ref({})

// 计算备份间隔文本
const backupIntervalText = computed(() => {
  const intervalMap = {
    '1 hour': '1小时',
    '1 day': '1天',
    '1 week': '1周',
    '1 month': '1个月'
  }
  return intervalMap[backupConfig.value.backup_interval] || backupConfig.value.backup_interval
})

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 获取备份配置
const getBackupConfig = async () => {
  try {
    const response = await fetch('/api/backup/config', {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'Content-Type': 'application/json'
      }
    })
    
    if (response.ok) {
      const data = await response.json()
      backupConfig.value = {
        backup_interval: data.backup_interval,
        keep_latest: data.keep_latest,
        is_enabled: data.is_enabled
      }
      backupPath.value = data.backup_path
      lastBackupTime.value = data.last_backup_at || '从未备份'
    } else {
      const error = await response.json()
      ElMessage.error(error.message || '获取备份配置失败')
    }
  } catch (error) {
    ElMessage.error('获取备份配置失败')
  }
}

// 更新备份配置函数已移除，因为配置只能通过配置文件修改

// 手动触发备份
const triggerBackup = async () => {
  triggerLoading.value = true
  try {
    const response = await fetch('/api/backup/trigger', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'Content-Type': 'application/json'
      }
    })
    
    if (response.ok) {
      ElMessage.success('备份已触发')
      // 刷新备份历史和配置
      await getBackupList()
      await getBackupConfig()
    } else {
      const error = await response.json()
      ElMessage.error(error.message || '触发备份失败')
    }
  } catch (error) {
    ElMessage.error('触发备份失败')
  } finally {
    triggerLoading.value = false
  }
}

// 获取备份历史
const getBackupList = async () => {
  try {
    const response = await fetch('/api/backup/list', {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'Content-Type': 'application/json'
      }
    })
    
    if (response.ok) {
      const data = await response.json()
      backupList.value = data
    } else {
      const error = await response.json()
      ElMessage.error(error.message || '获取备份历史失败')
    }
  } catch (error) {
    ElMessage.error('获取备份历史失败')
  }
}

// 恢复备份
const restoreBackup = async (filename) => {
  try {
    await ElMessageBox.confirm(
      `确定要恢复备份 "${filename}" 吗？这将覆盖当前数据库。`,
      '恢复备份',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    restoreLoading.value[filename] = true
    
    const response = await fetch(`/api/backup/restore/${filename}`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'Content-Type': 'application/json'
      }
    })
    
    if (response.ok) {
      ElMessage.success('备份恢复成功')
      // 刷新备份历史
      await getBackupList()
    } else {
      const error = await response.json()
      ElMessage.error(error.message || '恢复备份失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('恢复备份失败')
    }
  } finally {
    restoreLoading.value[filename] = false
  }
}

// 删除备份
const deleteBackup = async (filename) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除备份 "${filename}" 吗？`,
      '删除备份',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'danger'
      }
    )
    
    deleteLoading.value[filename] = true
    
    const response = await fetch(`/api/backup/delete/${filename}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'Content-Type': 'application/json'
      }
    })
    
    if (response.ok) {
      ElMessage.success('备份删除成功')
      // 刷新备份历史
      await getBackupList()
    } else {
      const error = await response.json()
      ElMessage.error(error.message || '删除备份失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除备份失败')
    }
  } finally {
    deleteLoading.value[filename] = false
  }
}

// 初始化
onMounted(async () => {
  await getBackupConfig()
  await getBackupList()
})
</script>

<style scoped>
.backup-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.card-header h2 {
  margin: 0;
  font-size: 18px;
  color: #303133;
}

.card-header h3 {
  margin: 0;
  font-size: 16px;
  color: #303133;
}

.mb-4 {
  margin-bottom: 20px;
}

.empty-backup {
  padding: 40px 0;
  display: flex;
  justify-content: center;
}
</style>