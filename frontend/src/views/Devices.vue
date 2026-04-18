<template>
  <div class="devices-container">
    <el-card class="mb-4">
      <div class="card-header">
        <h2>设备管理</h2>
        <el-button type="primary" @click="handleAddDevice">添加设备</el-button>
      </div>
    </el-card>

    <el-card>
      <el-table :data="devices" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80"></el-table-column>
        <el-table-column prop="device_model" label="设备型号"></el-table-column>
        <el-table-column prop="release_name" label="发布名称"></el-table-column>
        <el-table-column prop="description" label="设备描述"></el-table-column>
        <el-table-column prop="release_year" label="发布年份"></el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180"></el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="scope">
            <el-button type="primary" size="small" @click="handleEditDevice(scope.row)">编辑</el-button>
            <el-button type="danger" size="small" @click="handleDeleteDevice(scope.row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加/编辑设备对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="600px"
    >
      <el-form
        ref="deviceFormRef"
        :model="deviceForm"
        :rules="rules"
        label-width="100px"
      >
        <el-form-item label="设备型号" prop="device_model">
          <el-input v-model="deviceForm.device_model"></el-input>
        </el-form-item>
        <el-form-item label="发布名称" prop="release_name">
          <el-input v-model="deviceForm.release_name"></el-input>
        </el-form-item>
        <el-form-item label="设备描述">
          <el-input
            type="textarea"
            v-model="deviceForm.description"
            :rows="3"
            placeholder="请输入设备描述"
          ></el-input>
        </el-form-item>
        <el-form-item label="发布年份" prop="release_year">
          <el-input-number v-model="deviceForm.release_year" :min="2000" :max="2100"></el-input-number>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveDevice">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { deviceAPI } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const devices = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('添加设备')
const deviceFormRef = ref(null)

const deviceForm = reactive({
  id: '',
  name: '',
  device_model: '',
  description: '',
  release_name: '',
  release_year: new Date().getFullYear()
})

const rules = {
  device_model: [{ required: true, message: '请输入设备型号', trigger: 'blur' }],
  release_year: [{ required: true, message: '请输入发布年份', trigger: 'blur' }]
}

// 加载设备列表
const loadDevices = async () => {
  try {
    const response = await deviceAPI.getDevices()
    devices.value = response.data
  } catch (error) {
    ElMessage.error('加载设备列表失败')
  }
}

// 添加设备
const handleAddDevice = () => {
  deviceForm.id = ''
  deviceForm.name = ''
  deviceForm.device_model = ''
  deviceForm.description = ''
  deviceForm.release_name = ''
  deviceForm.release_year = new Date().getFullYear()
  dialogTitle.value = '添加设备'
  dialogVisible.value = true
}

// 编辑设备
const handleEditDevice = (device) => {
  deviceForm.id = device.id
  deviceForm.name = device.name
  deviceForm.device_model = device.device_model
  deviceForm.description = device.description
  deviceForm.release_name = device.release_name
  deviceForm.release_year = device.release_year
  dialogTitle.value = '编辑设备'
  dialogVisible.value = true
}

// 保存设备
const handleSaveDevice = async () => {
  if (!deviceFormRef.value) return
  
  await deviceFormRef.value.validate(async (valid) => {
    if (valid) {
      try {
        const data = {
          name: deviceForm.name,
          device_model: deviceForm.device_model,
          description: deviceForm.description,
          release_name: deviceForm.release_name,
          release_year: deviceForm.release_year,
          user_role: localStorage.getItem('role') || 'developer'
        }
        
        if (deviceForm.id) {
          // 更新设备
          await deviceAPI.updateDevice(deviceForm.id, data)
          ElMessage.success('设备更新成功')
        } else {
          // 添加设备
          await deviceAPI.createDevice(data)
          ElMessage.success('设备添加成功')
        }
        
        dialogVisible.value = false
        loadDevices()
      } catch (error) {
        ElMessage.error(error.response?.data?.message || '操作失败')
      }
    }
  })
}

// 删除设备
const handleDeleteDevice = async (id) => {
  try {
    await ElMessageBox.confirm('确定要删除该设备吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await deviceAPI.deleteDevice(id, {
      user_role: localStorage.getItem('role') || 'developer'
    })
    
    ElMessage.success('设备删除成功')
    loadDevices()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.message || '删除失败')
    }
  }
}

onMounted(() => {
  loadDevices()
})
</script>

<style scoped>
.devices-container {
  padding: 20px;
}

.mb-4 {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h2 {
  margin: 0;
  font-size: 18px;
}
</style>