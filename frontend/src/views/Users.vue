<template>
  <div class="users-container">
    <h2>用户管理</h2>
    <div class="user-actions">
      <el-button type="primary" @click="addUser">添加用户</el-button>
    </div>
    <el-table :data="users" style="width: 100%">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="username" label="用户名" />
      <el-table-column prop="role" label="角色">
          <template #default="scope">
            {{ scope.row.role === 'admin' ? '管理员' : '开发者' }}
          </template>
        </el-table-column>
      <el-table-column label="操作" width="240">
          <template #default="scope">
            <div style="display: flex; gap: 8px; align-items: center;">
              <el-button type="primary" size="small" @click="editUser(scope.row)">编辑</el-button>
              <el-button type="danger" size="small" @click="deleteUser(scope.row.id)">删除</el-button>
              <el-button type="success" size="small" @click="assignApps(scope.row)" v-if="scope.row.role === 'developer'">分配应用</el-button>
            </div>
          </template>
        </el-table-column>
    </el-table>

    <!-- 添加/编辑用户对话框 -->
    <el-dialog v-model="editDialogVisible" :title="isAddUser ? '添加用户' : '编辑用户'">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="editForm.username" :disabled="!isAddUser" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="editForm.role" placeholder="选择角色">
            <el-option label="管理员" value="admin" />
            <el-option label="开发" value="developer" />
          </el-select>
        </el-form-item>
        <el-form-item label="密码" prop="password" v-if="isAddUser">
          <el-input v-model="editForm.password" type="password" placeholder="请输入密码" />
        </el-form-item>
        <el-form-item label="密码" v-else>
          <el-input v-model="editForm.password" type="password" placeholder="留空则不修改" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveUser">确定</el-button>
      </template>
    </el-dialog>

    <!-- 分配应用对话框 -->
    <el-dialog v-model="assignDialogVisible" title="分配应用">
      <el-form label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="currentUser.username" disabled />
        </el-form-item>
        <el-form-item label="可选应用">
          <el-checkbox-group v-model="selectedApps">
            <el-checkbox v-for="app in apps" :key="app.id" :label="app.id">
              {{ app.name }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveAppAssignments">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { featureAPI } from '../api'
import { ElMessage } from 'element-plus'

const users = ref([])
const apps = ref([])
const editDialogVisible = ref(false)
const assignDialogVisible = ref(false)
const editForm = ref({})
const currentUser = ref({})
const selectedApps = ref([])
const isAddUser = ref(false)

// 获取用户列表
const getUsers = async () => {
  try {
    const response = await fetch('http://localhost:5001/api/users')
    const data = await response.json()
    users.value = data
  } catch (error) {
    ElMessage.error('获取用户列表失败')
  }
}

// 获取应用列表
const getApps = async () => {
  try {
    let userRole = 'admin'
    let user_id = '1'
    try {
      userRole = localStorage.getItem('role') || 'admin'
      user_id = localStorage.getItem('user_id') || '1'
    } catch (error) {
      console.error('Error getting localStorage:', error)
    }
    
    const response = await featureAPI.getFeatures(userRole, user_id, { page: 1, page_size: 100 })
    const data = response.data.data
    apps.value = data.filter(item => item.node_type === 'app')
  } catch (error) {
    ElMessage.error('获取应用列表失败')
  }
}

// 添加用户
const addUser = () => {
  isAddUser.value = true
  editForm.value = {
    username: '',
    password: '',
    role: 'developer'
  }
  editDialogVisible.value = true
}

// 编辑用户
const editUser = (user) => {
  isAddUser.value = false
  editForm.value = { ...user }
  editDialogVisible.value = true
}

// 保存用户
const saveUser = async () => {
  try {
    if (isAddUser.value) {
      // 添加用户
      const response = await fetch('http://localhost:5001/api/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          username: editForm.value.username,
          password: editForm.value.password,
          role: editForm.value.role,
          user_role: 'admin' // 管理员操作
        })
      })
      const data = await response.json()
      if (response.ok) {
        ElMessage.success('用户添加成功')
        getUsers()
        editDialogVisible.value = false
      } else {
        ElMessage.error(data.message || '用户添加失败')
      }
    } else {
      // 更新用户
      const response = await fetch(`http://localhost:5001/api/users/${editForm.value.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(editForm.value)
      })
      const data = await response.json()
      if (response.ok) {
        ElMessage.success('用户更新成功')
        getUsers()
        editDialogVisible.value = false
      } else {
        ElMessage.error(data.message || '用户更新失败')
      }
    }
  } catch (error) {
    ElMessage.error('网络错误')
  }
}

// 删除用户
const deleteUser = async (id) => {
  try {
    const response = await fetch(`http://localhost:5001/api/users/${id}`, {
      method: 'DELETE'
    })
    const data = await response.json()
    if (response.ok) {
      ElMessage.success('用户删除成功')
      getUsers()
    } else {
      ElMessage.error(data.message || '用户删除失败')
    }
  } catch (error) {
    ElMessage.error('网络错误')
  }
}

// 分配应用
const assignApps = async (user) => {
  currentUser.value = { ...user }
  // 获取用户已分配的应用
  try {
    const response = await fetch(`http://localhost:5001/api/user-apps/${user.id}`)
    const data = await response.json()
    selectedApps.value = data.map(item => item.app_id)
    getApps()
    assignDialogVisible.value = true
  } catch (error) {
    ElMessage.error('获取用户应用分配失败')
  }
}

// 保存应用分配
const saveAppAssignments = async () => {
  try {
    // 先删除用户现有的应用分配
    const response = await fetch(`http://localhost:5001/api/user-apps/${currentUser.value.id}`)
    const existingAssignments = await response.json()
    for (const assignment of existingAssignments) {
      await fetch(`http://localhost:5001/api/user-apps/${assignment.id}`, {
        method: 'DELETE'
      })
    }
    // 添加新的应用分配
    for (const appId of selectedApps.value) {
      await fetch('http://localhost:5001/api/user-apps', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          user_id: currentUser.value.id,
          app_id: appId
        })
      })
    }
    ElMessage.success('应用分配成功')
    assignDialogVisible.value = false
  } catch (error) {
    ElMessage.error('应用分配失败')
  }
}

// 初始化
onMounted(() => {
  getUsers()
  getApps()
})
</script>

<style scoped>
.users-container {
  padding: 20px;
}

.users-container h2 {
  margin-bottom: 20px;
  color: #303133;
}

.el-table {
  margin-bottom: 20px;
}

.el-dialog {
  width: 500px;
}

.el-checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>