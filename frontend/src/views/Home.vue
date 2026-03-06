<template>
  <div class="home-container">
    <el-container>
      <el-aside width="200px" class="sidebar">
        <div class="logo">
          <h3>App功能管理</h3>
        </div>
        <el-menu
          :default-active="activeMenu"
          class="el-menu-vertical-demo"
          router
          @select="handleMenuSelect"
        >
          <el-menu-item index="/features">
            <el-icon><i-ep-menu /></el-icon>
            <span>功能管理</span>
          </el-menu-item>
          <el-menu-item index="/statistics">
            <el-icon><i-ep-data-analysis /></el-icon>
            <span>数据统计</span>
          </el-menu-item>
          <el-menu-item index="/users" v-if="isAdmin">
            <el-icon><i-ep-user /></el-icon>
            <span>用户管理</span>
          </el-menu-item>
          <el-menu-item index="/audit/approval" v-if="isAdmin">
            <el-icon><i-ep-timer /></el-icon>
            <span>审核审批</span>
          </el-menu-item>
          <el-menu-item index="/audit/log">
            <el-icon><i-ep-document /></el-icon>
            <span>审核日志</span>
          </el-menu-item>
          <el-menu-item index="/backup" v-if="isAdmin">
            <el-icon><i-ep-back /></el-icon>
            <span>备份管理</span>
          </el-menu-item>
          <el-menu-item index="/devices" v-if="isAdmin">
            <el-icon><i-ep-monitor /></el-icon>
            <span>设备管理</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      <el-container>
        <el-header class="header">
          <div class="header-right">
            <el-dropdown>
              <span class="user-info">
                欢迎，{{ username }}
                <el-icon class="el-icon--right"><i-ep-arrow-down /></el-icon>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="showChangePasswordDialog = true">修改密码</el-dropdown-item>
                  <el-dropdown-item @click="handleLogout">退出登录</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </el-header>

        <!-- 修改密码对话框 -->
        <el-dialog v-model="showChangePasswordDialog" title="修改密码" width="400px">
          <el-form :model="changePasswordForm" :rules="changePasswordRules" ref="changePasswordFormRef" label-width="100px">
            <el-form-item label="原密码" prop="old_password">
              <el-input v-model="changePasswordForm.old_password" type="password" placeholder="请输入原密码" />
            </el-form-item>
            <el-form-item label="新密码" prop="new_password">
              <el-input v-model="changePasswordForm.new_password" type="password" placeholder="请输入新密码" />
            </el-form-item>
            <el-form-item label="确认新密码" prop="confirm_password">
              <el-input v-model="changePasswordForm.confirm_password" type="password" placeholder="请确认新密码" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="showChangePasswordDialog = false">取消</el-button>
            <el-button type="primary" @click="handleChangePassword" :loading="changePasswordLoading">确定</el-button>
          </template>
        </el-dialog>
        <el-main class="main-content">
          <router-view />
        </el-main>
        <el-footer class="footer">
          <div class="footer-content">
            <span>copyright Huawei，Author by Ning Lu Vibe coding</span>
          </div>
        </el-footer>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authAPI } from '../api'

const router = useRouter()
const route = useRoute()
const username = ref(localStorage.getItem('username') || '管理员')

const activeMenu = computed(() => {
  return route.path
})

const isAdmin = computed(() => {
  return localStorage.getItem('role') === 'admin'
})

// 修改密码相关
const showChangePasswordDialog = ref(false)
const changePasswordLoading = ref(false)
const changePasswordFormRef = ref(null)
const changePasswordForm = ref({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

const changePasswordRules = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [{ required: true, message: '请输入新密码', trigger: 'blur' }],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== changePasswordForm.value.new_password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

const handleMenuSelect = (key, keyPath) => {
  // 菜单选择处理
}

const handleLogout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('role')
  localStorage.removeItem('username')
  localStorage.removeItem('user_id')
  ElMessage.success('退出登录成功')
  router.push('/login')
}

const handleChangePassword = async () => {
  if (!changePasswordFormRef.value) return
  
  await changePasswordFormRef.value.validate(async (valid) => {
    if (valid) {
      changePasswordLoading.value = true
      try {
        const response = await authAPI.changePassword({
          username: username.value,
          old_password: changePasswordForm.value.old_password,
          new_password: changePasswordForm.value.new_password
        })
        ElMessage.success('密码修改成功')
        showChangePasswordDialog.value = false
        // 重置表单
        changePasswordForm.value = {
          old_password: '',
          new_password: '',
          confirm_password: ''
        }
      } catch (error) {
        ElMessage.error(error.response?.data?.message || '密码修改失败，请检查原密码是否正确')
      } finally {
        changePasswordLoading.value = false
      }
    }
  })
}

onMounted(() => {
  // 可以在这里获取用户信息
})
</script>

<style scoped>
.home-container {
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.sidebar {
  background-color: #2c3e50;
  color: white;
  height: 100vh;
  position: relative;
  z-index: 5;
  padding-bottom: 40px;
}

.logo {
  padding: 20px;
  text-align: center;
  border-bottom: 1px solid #34495e;
}

.logo h3 {
  margin: 0;
  color: white;
}

.el-menu-vertical-demo {
  background-color: #2c3e50;
  border-right: none;
}

/* 普通菜单项样式 */
.el-menu-item {
  color: #ecf0f1;
}

.el-menu-item:hover {
  color: white;
  background-color: rgba(52, 152, 219, 0.2);
}

.el-menu-item.is-active {
  background-color: #3498db;
  color: white;
}

/* 下拉菜单样式 */
.el-sub-menu {
  color: #ecf0f1;
}

.el-sub-menu .el-sub-menu__title {
  color: #ecf0f1;
}

.el-sub-menu .el-sub-menu__title:hover {
  color: white;
  background-color: rgba(52, 152, 219, 0.2);
}

.el-sub-menu .el-sub-menu__title.is-active {
  color: white;
  background-color: #3498db;
}

/* 下拉菜单项样式 */
.el-sub-menu .el-menu-item {
  color: #ecf0f1;
}

.el-sub-menu .el-menu-item:hover {
  color: white;
  background-color: rgba(52, 152, 219, 0.2);
}

.el-sub-menu .el-menu-item.is-active {
  color: white;
  background-color: #3498db;
}

.header {
  background-color: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: flex-end;
  align-items: center;
  padding: 0 20px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 20px;
}

.user-info {
  font-size: 14px;
  color: #303133;
}

.main-content {
  background-color: #f5f7fa;
  padding: 20px;
  padding-bottom: 60px;
  overflow-y: auto;
  flex: 1;
}

.footer {
  background-color: white;
  border-top: 1px solid #ebeef5;
  padding: 10px 20px;
  height: auto;
  min-height: 40px;
  margin-top: auto;
  width: 100vw;
  position: absolute;
  bottom: 0;
  left: 0;
  z-index: 10;
}

.footer-content {
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 12px;
  color: #909399;
  width: 100%;
}

/* 确保容器布局正确 */
:deep(.el-container) {
  display: flex;
  flex-direction: column;
  height: 100%;
}

:deep(.el-container:first-child) {
  flex-direction: row;
}

:deep(.el-container:nth-child(2)) {
  flex-direction: column;
  flex: 1;
}
</style>
