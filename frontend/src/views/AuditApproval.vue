<style scoped>
.detail-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.detail-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.detail-label {
  font-weight: bold;
  color: #303133;
  min-width: 100px;
  flex-shrink: 0;
}

.detail-value {
  flex: 1;
  color: #606266;
  word-break: break-word;
}

.description-preview {
  cursor: pointer;
  line-height: 1.5;
}

.description-preview:hover {
  color: #409eff;
}
</style>

<template>
  <div class="audit-approval-container">
    <h2>审核审批</h2>
    
    <!-- 过滤和分页控件 -->
    <div class="filter-pagination-container">
      <div class="filter-section">
        <el-date-picker
          v-model="dateFilter"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          @change="handleDateFilter"
        />
        <el-button type="primary" @click="resetFilter">重置</el-button>
      </div>
    </div>
    
    <div class="el-table-container">
      <el-table :data="paginatedAuditLogs" style="width: 100%" size="small">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="app_name" label="应用" />
        <el-table-column prop="feature_name" label="功能名称" />
        <el-table-column prop="action" label="操作类型">
          <template #default="scope">
            {{ getActionText(scope.row.action) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态">
          <template #default="scope">
            {{ getStatusText(scope.row.status) }}
          </template>
        </el-table-column>
        <el-table-column prop="created_by" label="创建者" />
        <el-table-column prop="created_at" label="创建时间">
          <template #default="scope">
            {{ formatDateTime(scope.row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="详情" width="240">
          <template #default="scope">
            <div style="display: flex; gap: 8px; align-items: center;">
              <el-button type="primary" size="small" @click="viewDetails(scope.row)">查看详情</el-button>
              <el-button type="success" size="small" @click="approveAudit(scope.row.id)">通过</el-button>
              <el-button type="danger" size="small" @click="rejectAudit(scope.row.id)">拒绝</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>
    
    <!-- 分页组件 -->
    <div class="pagination-section">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        :total="auditLogs.length"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>

    <!-- 审核详情对话框 -->
    <el-dialog v-model="detailDialogVisible" title="审核详情" width="900px">
      <div class="audit-detail-content">
        <!-- 基本信息卡片 -->
        <el-card class="info-card mb-4">
          <template #header>
            <div class="card-header">
              <span class="card-title">审核基本信息</span>
              <el-tag :type="getStatusType(currentAudit.status)">{{ getStatusText(currentAudit.status) }}</el-tag>
            </div>
          </template>
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">审核ID：</span>
              <span class="info-value">{{ currentAudit.id }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">功能ID：</span>
              <span class="info-value">{{ currentAudit.feature_id }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">功能名称：</span>
              <span class="info-value feature-name">{{ currentAudit.feature_name || '未知功能' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">应用：</span>
              <span class="info-value">{{ currentAudit.app_name || '未知应用' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">操作类型：</span>
              <span class="info-value">{{ getActionText(currentAudit.action) }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">创建者：</span>
              <span class="info-value">{{ currentAudit.created_by }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">创建时间：</span>
              <span class="info-value">{{ formatDateTime(currentAudit.created_at) }}</span>
            </div>
          </div>
        </el-card>

        <!-- 根据操作类型显示不同的详情 -->
        <div v-if="currentAudit.action === 'delete'" class="action-detail">
          <el-card class="action-card mb-4">
            <template #header>
              <div class="card-header">
                <span class="card-title">删除功能详情</span>
              </div>
            </template>
            <div class="action-content">
              <p class="action-description">该操作将删除以下功能：</p>
              <p class="feature-name">{{ currentAudit.feature_name || '未知功能' }}</p>
              <div v-if="currentAudit.before_content" class="feature-details mt-4">
                <h5 class="section-title">删除前内容</h5>
                <div class="feature-panel">
                  <RenderFeatureDetails :content="currentAudit.before_content" />
                </div>
              </div>
            </div>
          </el-card>
        </div>

        <div v-else-if="currentAudit.action === 'create'" class="action-detail">
          <el-card class="action-card mb-4">
            <template #header>
              <div class="card-header">
                <span class="card-title">新增功能详情</span>
              </div>
            </template>
            <div class="action-content">
              <p class="action-description">该操作将新增以下功能：</p>
              <p class="feature-name">{{ currentAudit.feature_name || '未知功能' }}</p>
              <div v-if="currentAudit.after_content" class="feature-details mt-4">
                <h5 class="section-title">新增内容</h5>
                <div class="feature-panel">
                  <RenderFeatureDetails :content="currentAudit.after_content" />
                </div>
              </div>
            </div>
          </el-card>
        </div>

        <div v-else-if="currentAudit.action === 'update'" class="action-detail">
          <el-card class="action-card mb-4">
            <template #header>
              <div class="card-header">
                <span class="card-title">修改功能详情</span>
              </div>
            </template>
            <div class="comparison-content">
              <div class="comparison-row">
                <div class="comparison-panel">
                  <div class="panel-header">
                    <span class="panel-title">修改前</span>
                  </div>
                  <div class="panel-content">
                    <div v-if="currentAudit.before_content">
                      <RenderFeatureDetails :content="currentAudit.before_content" />
                    </div>
                    <p v-else class="no-content">无修改前内容</p>
                  </div>
                </div>
                <div class="comparison-arrow">
                  <el-icon class="arrow-icon"><ArrowRight /></el-icon>
                </div>
                <div class="comparison-panel">
                  <div class="panel-header">
                    <span class="panel-title">修改后</span>
                  </div>
                  <div class="panel-content">
                    <div v-if="currentAudit.after_content">
                      <RenderFeatureDetails :content="currentAudit.after_content" />
                    </div>
                    <p v-else class="no-content">无修改后内容</p>
                  </div>
                </div>
              </div>
            </div>
          </el-card>
        </div>
      </div>
      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, h } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowRight } from '@element-plus/icons-vue'
import { marked } from 'marked'

// 渲染功能详情组件
const RenderFeatureDetails = {
  props: {
    content: {
      type: String,
      required: true
    }
  },
  setup(props) {
    const parsedContent = computed(() => {
      try {
        return JSON.parse(props.content)
      } catch (error) {
        try {
          const cleanedContent = props.content
            .replace(/'/g, '"')
            .replace(/None/g, 'null')
            .replace(/True/g, 'true')
            .replace(/False/g, 'false')
          return JSON.parse(cleanedContent)
        } catch (error) {
          return null
        }
      }
    })

    const renderedDescription = computed(() => {
      if (!parsedContent.value) return ''
      return marked(parsedContent.value.description || '')
    })

    return () => {
      if (!parsedContent.value) {
        return h('p', '无法解析内容')
      }

      const content = parsedContent.value
      
      const getLabelsByNodeType = (nodeType) => {
        switch (nodeType) {
          case 'app':
            return {
              name: '应用名称',
              description: '应用描述'
            }
          case 'category':
            return {
              name: '分类名称',
              description: '分类描述'
            }
          case 'function':
            return {
              name: '功能名称',
              description: '功能描述'
            }
          default:
            return {
              name: '节点名称',
              description: '节点描述'
            }
        }
      }
      
      const labels = getLabelsByNodeType(content.node_type)
      
      // 构建详情列表
      const detailItems = []
      
      // 添加名称字段
      detailItems.push(
        h('div', {
          class: 'detail-item'
        }, [
          h('span', {
            class: 'detail-label'
          }, labels.name + '：'),
          h('span', {
            class: 'detail-value'
          }, content.name || '无')
        ])
      )
      
      // 添加描述字段
      detailItems.push(
        h('div', {
          class: 'detail-item'
        }, [
          h('span', {
            class: 'detail-label'
          }, labels.description + '：'),
          h('div', {
            class: 'detail-value description-preview',
            innerHTML: renderedDescription.value || '<p>无</p>'
          })
        ])
      )

      // 对于功能节点，添加所有可能的字段，即使它们在数据中不存在
      if (content.node_type === 'function') {
        // 添加典型使用案例
        detailItems.push(
          h('div', {
            class: 'detail-item'
          }, [
            h('span', {
              class: 'detail-label'
            }, '典型使用案例：'),
            h('span', {
              class: 'detail-value'
            }, content.use_cases || '无')
          ])
        )
        
        // 添加教学视频
        detailItems.push(
          h('div', {
            class: 'detail-item'
          }, [
            h('span', {
              class: 'detail-label'
            }, '教学视频：'),
            h('span', {
              class: 'detail-value'
            }, content.videos || '无')
          ])
        )
        
        // 添加版本范围
        detailItems.push(
          h('div', {
            class: 'detail-item'
          }, [
            h('span', {
              class: 'detail-label'
            }, '版本范围：'),
            h('span', {
              class: 'detail-value'
            }, content.version_range || 'All')
          ])
        )
        
        // 添加是否支持引导
        detailItems.push(
          h('div', {
            class: 'detail-item'
          }, [
            h('span', {
              class: 'detail-label'
            }, '是否支持引导：'),
            h('span', {
              class: 'detail-value'
            }, (content.is_guide_supported === true || content.is_guide_supported === 'true') ? '是' : '否')
          ])
        )
      }

      return h('div', {
        class: 'detail-list'
      }, detailItems)
    }
  }
}

const auditLogs = ref([])
const detailDialogVisible = ref(false)
const currentAudit = ref({})
const currentPage = ref(1)
const pageSize = ref(20)
const dateFilter = ref([])
const filteredAuditLogs = ref([])

const isAdmin = computed(() => {
  try {
    return localStorage.getItem('role') === 'admin'
  } catch (error) {
    return false
  }
})

const pendingAuditLogs = computed(() => {
  return auditLogs.value.filter(log => log.status === 'pending')
})

const paginatedAuditLogs = computed(() => {
  const logs = filteredAuditLogs.value.length > 0 ? filteredAuditLogs.value : pendingAuditLogs.value
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return logs.slice(start, end)
})

const getAuditLogs = async () => {
  try {
    let url = 'http://localhost:5001/api/audit-logs'
    const params = new URLSearchParams()
    
    if (Array.isArray(dateFilter.value) && dateFilter.value.length === 2) {
      params.append('start_date', dateFilter.value[0])
      params.append('end_date', dateFilter.value[1])
    } else if (dateFilter.value) {
      params.append('date', dateFilter.value)
    }
    
    if (params.toString()) {
      url += `?${params.toString()}`
    }
    
    const response = await fetch(url)
    const data = await response.json()
    auditLogs.value = data
    filteredAuditLogs.value = []
  } catch (error) {
    ElMessage.error('获取审核日志失败')
  }
}

const handleSizeChange = (size) => {
  pageSize.value = size
  currentPage.value = 1
}

const handleCurrentChange = (current) => {
  currentPage.value = current
}

const handleDateFilter = () => {
  currentPage.value = 1
  getAuditLogs()
}

const resetFilter = () => {
  dateFilter.value = []
  currentPage.value = 1
  getAuditLogs()
}

const getActionText = (action) => {
  const actionMap = {
    'create': '新增',
    'update': '修改',
    'delete': '删除'
  }
  return actionMap[action] || action
}

const getStatusText = (status) => {
  const statusMap = {
    'pending': '待审核',
    'approved': '已通过',
    'rejected': '已拒绝',
    'withdrawn': '已撤回'
  }
  return statusMap[status] || status
}

// 根据状态获取标签类型
const getStatusType = (status) => {
  const typeMap = {
    'pending': 'warning',
    'approved': 'success',
    'rejected': 'danger'
  }
  return typeMap[status] || 'info'
}

// 格式化日期时间为 YY-MM-DD hh:mm:ss 格式
const formatDateTime = (dateTimeString) => {
  if (!dateTimeString) return ''
  
  const date = new Date(dateTimeString)
  if (isNaN(date.getTime())) return dateTimeString
  
  const year = date.getFullYear().toString().slice(2) // 只取后两位年份
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}

const viewDetails = (audit) => {
  currentAudit.value = { ...audit }
  detailDialogVisible.value = true
}

const approveAudit = async (id) => {
  try {
    const response = await fetch(`http://localhost:5001/api/audit-logs/${id}/approve`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        approved_by: localStorage.getItem('username') || 'admin'
      })
    })
    const data = await response.json()
    if (response.ok) {
      ElMessage.success('审核通过')
      getAuditLogs()
    } else {
      ElMessage.error(data.message || '审核失败')
    }
  } catch (error) {
    ElMessage.error('网络错误')
  }
}

const rejectAudit = async (id) => {
  try {
    const response = await fetch(`http://localhost:5001/api/audit-logs/${id}/reject`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        approved_by: localStorage.getItem('username') || 'admin'
      })
    })
    const data = await response.json()
    if (response.ok) {
      ElMessage.success('审核拒绝')
      getAuditLogs()
    } else {
      ElMessage.error(data.message || '审核失败')
    }
  } catch (error) {
    ElMessage.error('网络错误')
  }
}

onMounted(() => {
  getAuditLogs()
})
</script>

<style scoped>
.audit-approval-container {
  padding: 0;
}

.audit-approval-container h2 {
  margin-bottom: 20px;
  color: #303133;
}

.filter-pagination-container {
  margin-bottom: 20px;
}

.filter-section {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 15px;
}

.pagination-section {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
  align-items: center;
}

.el-table-container {
  max-height: calc(100vh - 300px);
  overflow: auto;
  border: 1px solid #ebeef5;
  border-radius: 4px;
}

.el-table__header-wrapper,
.el-table__body-wrapper {
  overflow: auto;
}

.el-table th,
.el-table td {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding: 8px 12px;
  line-height: 1.4;
}

.el-table-column {
  min-width: 100px;
}

::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}

::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

.audit-detail-content {
  max-height: 600px;
  overflow-y: auto;
}

.mb-4 {
  margin-bottom: 20px;
}

/* 卡片样式 */
.info-card,
.action-card {
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background-color: #f9f9f9;
  border-bottom: 1px solid #ebeef5;
  border-radius: 8px 8px 0 0;
}

.card-title {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
}

/* 信息网格样式 */
.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 12px;
  padding: 16px;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.info-label {
  font-size: 14px;
  color: #606266;
  font-weight: 500;
  min-width: 90px;
}

.info-value {
  font-size: 14px;
  color: #303133;
  flex: 1;
}

/* 功能名称样式 */
.feature-name {
  font-weight: bold;
  color: #409eff;
  margin: 8px 0;
  font-size: 15px;
}

/* 操作详情样式 */
.action-content {
  padding: 20px;
}

.action-description {
  font-size: 14px;
  color: #606266;
  margin-bottom: 12px;
}

.section-title {
  font-size: 14px;
  font-weight: bold;
  color: #303133;
  margin-bottom: 12px;
  padding-bottom: 6px;
  border-bottom: 1px solid #ebeef5;
}

.feature-panel {
  background-color: #f9f9f9;
  padding: 16px;
  border-radius: 4px;
  border: 1px solid #ebeef5;
}

/* 比较内容样式 */
.comparison-content {
  padding: 20px;
}

.comparison-row {
  display: flex;
  align-items: flex-start;
  gap: 20px;
}

.comparison-panel {
  flex: 1;
  min-width: 0;
  background-color: #f9f9f9;
  border-radius: 4px;
  border: 1px solid #ebeef5;
  overflow: hidden;
}

.comparison-panel .panel-header {
  padding: 12px 16px;
  background-color: #f0f2f5;
  border-bottom: 1px solid #ebeef5;
}

.comparison-panel .panel-title {
  font-size: 14px;
  font-weight: bold;
  color: #303133;
}

.comparison-panel .panel-content {
  padding: 16px;
}

.comparison-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px 0;
  color: #909399;
}

.arrow-icon {
  font-size: 24px;
}

.no-content {
  color: #909399;
  text-align: center;
  padding: 20px 0;
  margin: 0;
}

/* 响应式设计 */
@media screen and (max-width: 768px) {
  .info-grid {
    grid-template-columns: 1fr;
  }
  
  .comparison-row {
    flex-direction: column;
  }
  
  .comparison-arrow {
    transform: rotate(90deg);
    padding: 10px 0;
  }
}

.description-preview {
  max-height: 300px;
  overflow-y: auto;
  padding: 15px;
  background-color: #f9f9f9;
  border-radius: 4px;
  font-size: 14px;
  line-height: 1.6;
  cursor: pointer;
  transition: background-color 0.3s;
}

.description-preview:hover {
  background-color: #f0f0f0;
}

.description-preview h1,
.description-preview h2,
.description-preview h3 {
  margin: 10px 0;
  font-size: 16px;
  font-weight: bold;
}

.description-preview p {
  margin: 5px 0;
}

.video-link {
  color: #409eff;
  text-decoration: none;
  margin-right: 10px;
}

.video-link:hover {
  text-decoration: underline;
}

@media screen and (max-width: 768px) {
  .comparison-panels {
    flex-direction: column;
  }
}
</style>