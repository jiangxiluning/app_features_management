<template>
  <div class="statistics-container">
    <el-card class="mb-4">
      <h2>数据统计</h2>
      <p>系统功能知识管理数据统计分析</p>
    </el-card>

    <!-- 全局统计卡片 -->
    <div class="stats-cards">
      <el-card class="stats-card">
        <div class="stats-item">
            <el-icon class="stats-icon"><i-ep-data-line /></el-icon>
            <div class="stats-info">
              <div class="stats-value">{{ globalStats.total_apps }}</div>
              <div class="stats-label">应用数</div>
            </div>
          </div>
      </el-card>
      <el-card class="stats-card">
        <div class="stats-item">
          <el-icon class="stats-icon"><i-ep-folder /></el-icon>
          <div class="stats-info">
            <div class="stats-value">{{ globalStats.total_categories }}</div>
            <div class="stats-label">分类数</div>
          </div>
        </div>
      </el-card>
      <el-card class="stats-card">
        <div class="stats-item">
          <el-icon class="stats-icon"><i-ep-data-analysis /></el-icon>
          <div class="stats-info">
            <div class="stats-value">{{ globalStats.total_features }}</div>
            <div class="stats-label">功能数</div>
          </div>
        </div>
      </el-card>
      <el-card class="stats-card">
        <div class="stats-item">
          <el-icon class="stats-icon"><i-ep-video-camera /></el-icon>
          <div class="stats-info">
            <div class="stats-value">{{ globalStats.total_videos }}</div>
            <div class="stats-label">教学视频数</div>
          </div>
        </div>
      </el-card>
      <el-card class="stats-card">
        <div class="stats-item">
          <el-icon class="stats-icon"><i-ep-warning /></el-icon>
          <div class="stats-info">
            <div class="stats-value">{{ globalStats.pending_total || 0 }}</div>
            <div class="stats-label">未审核节点</div>
          </div>
        </div>
      </el-card>
      <el-card class="stats-card">
        <div class="stats-item">
          <el-icon class="stats-icon"><i-ep-document /></el-icon>
          <div class="stats-info">
            <div class="stats-value">{{ globalStats.pending_features || 0 }}</div>
            <div class="stats-label">未审核功能</div>
          </div>
        </div>
      </el-card>
      <el-card class="stats-card">
        <div class="stats-item">
          <el-icon class="stats-icon"><i-ep-folder-opened /></el-icon>
          <div class="stats-info">
            <div class="stats-value">{{ globalStats.pending_categories || 0 }}</div>
            <div class="stats-label">未审核分类</div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 应用统计 -->
    <el-card class="mb-4">
      <h3>应用统计</h3>
      <div class="app-stats">
        <el-empty v-if="appStats.length === 0" description="暂无应用数据" />
        <div v-else class="app-stats-grid">
          <el-card v-for="app in appStats" :key="app.id" class="app-stats-card">
            <div class="app-stats-header">
              <el-icon><i-ep-monitor /></el-icon>
              <h4>{{ app.name }}</h4>
            </div>
            <div class="app-stats-content">
              <div class="app-stats-item">
                <div class="app-stats-value">{{ app.total_features }}</div>
                <div class="app-stats-label">功能数</div>
              </div>
              <div class="app-stats-item">
                <div class="app-stats-value">{{ app.total_categories }}</div>
                <div class="app-stats-label">分类数</div>
              </div>
              <div class="app-stats-item">
                <div class="app-stats-value">{{ app.total_videos }}</div>
                <div class="app-stats-label">视频数</div>
              </div>
              <div class="app-stats-item pending">
                <div class="app-stats-value">{{ app.pending_total || 0 }}</div>
                <div class="app-stats-label">未审核节点</div>
              </div>
              <div class="app-stats-item pending">
                <div class="app-stats-value">{{ app.pending_features || 0 }}</div>
                <div class="app-stats-label">未审核功能</div>
              </div>
              <div class="app-stats-item pending">
                <div class="app-stats-value">{{ app.pending_categories || 0 }}</div>
                <div class="app-stats-label">未审核分类</div>
              </div>
            </div>
          </el-card>
        </div>
      </div>
    </el-card>

    <!-- 功能分类分布 -->
    <el-card class="mb-4">
      <h3>功能分类分布</h3>
      <div class="chart-container">
        <el-empty v-if="categoryDistribution.length === 0" description="暂无数据" />
        <div v-else class="pie-chart">
          <el-progress
            v-for="item in categoryDistribution"
            :key="item.category"
            :percentage="item.percentage"
            :format="() => `${item.category}: ${item.count} (${item.percentage}%)`"
            :color="getProgressColor(item.percentage)"
            :stroke-width="15"
          />
        </div>
      </div>
    </el-card>

    <!-- 最近添加的功能 -->
    <el-card>
      <h3>最近添加的功能</h3>
      <el-table :data="recentFeatures" style="width: 100%">
        <el-table-column prop="name" label="功能名称" />
        <el-table-column prop="app_name" label="应用" width="120" />
        <el-table-column prop="category_name" label="分类" width="200" />
        <el-table-column prop="created_at" label="添加时间" width="180" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { featureAPI, statisticsAPI } from '../api'
import { ElMessage } from 'element-plus'

// 统计数据
const globalStats = ref({
  total_apps: 0,
  total_features: 0,
  total_categories: 0,
  total_videos: 0
})
const appStats = ref([])
const categoryDistribution = ref([])
const recentFeatures = ref([])

// 加载统计数据
const loadStatistics = async () => {
  try {
    // 加载统计数据
    const statsResponse = await statisticsAPI.getStatistics()
    globalStats.value = statsResponse.data.global
    appStats.value = statsResponse.data.apps
    
    // 加载功能数据用于分类分布和最近添加
    let userRole = 'admin'
    let user_id = '1'
    try {
      userRole = localStorage.getItem('role') || 'admin'
      user_id = localStorage.getItem('user_id') || '1'
    } catch (error) {
      console.error('Error getting localStorage:', error)
    }
    
    const featuresResponse = await featureAPI.getFeatures(userRole, user_id, { page: 1, page_size: 100 })
    const features = featuresResponse.data.data
    
    // 递归获取所有功能节点
    const getAllFunctions = (nodes) => {
      let functions = []
      nodes.forEach(node => {
        if (node.node_type === 'function') {
          functions.push(node)
        }
        if (node.children && node.children.length > 0) {
          functions = [...functions, ...getAllFunctions(node.children)]
        }
      })
      return functions
    }
    
    // 获取所有功能节点
    const allFunctions = getAllFunctions(features)
    
    // 计算分类分布
    const categoryCount = {}
    allFunctions.forEach(feature => {
      if (feature.parent) {
        if (feature.parent.node_type === 'category') {
          const categoryName = feature.parent.name
          categoryCount[categoryName] = (categoryCount[categoryName] || 0) + 1
        } else if (feature.parent.node_type === 'app') {
          // 对于直接在应用下的功能，使用应用名称作为分类
          const categoryName = feature.parent.name
          categoryCount[categoryName] = (categoryCount[categoryName] || 0) + 1
        }
      }
    })
    
    const distribution = []
    const totalFunctions = Object.values(categoryCount).reduce((sum, count) => sum + count, 0)
    if (totalFunctions > 0) {
      Object.entries(categoryCount).forEach(([category, count]) => {
        const percentage = Math.round((count / totalFunctions) * 100)
        distribution.push({ category, count, percentage })
      })
    }
    categoryDistribution.value = distribution
    
    // 获取最近添加的功能（按创建时间倒序）
    recentFeatures.value = [...allFunctions]
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
      .slice(0, 5)
      
    // 从整个功能树中查找节点
    const findNodeById = (nodes, id) => {
      for (const node of nodes) {
        if (node.id === id) {
          return node
        }
        if (node.children && node.children.length > 0) {
          const found = findNodeById(node.children, id)
          if (found) {
            return found
          }
        }
      }
      return null
    }
    
    // 获取功能的完整分类路径
    const getCategoryPath = (feature) => {
      const path = []
      let currentId = feature.parent_id
      
      // 向上遍历，直到找到应用节点或根节点
      while (currentId) {
        const currentNode = findNodeById(features, currentId)
        if (!currentNode) {
          break
        }
        
        if (currentNode.node_type === 'category') {
          path.unshift(currentNode.name)
        } else if (currentNode.node_type === 'app') {
          break
        }
        
        currentId = currentNode.parent_id
      }
      
      return path.join('-')
    }
    
    // 为最近添加的功能添加应用名称和层级分类路径
    recentFeatures.value = recentFeatures.value.map(feature => {
      let appName = '未知'
      let categoryPath = ''
      
      // 查找应用名称
      let currentId = feature.parent_id
      while (currentId) {
        const currentNode = findNodeById(features, currentId)
        if (!currentNode) {
          break
        }
        
        if (currentNode.node_type === 'app') {
          appName = currentNode.name
          break
        }
        
        currentId = currentNode.parent_id
      }
      
      // 获取分类路径
      categoryPath = getCategoryPath(feature)
      
      return {
        ...feature,
        app_name: appName,
        category_name: categoryPath || '直接在应用下'
      }
    })
      
  } catch (error) {
    ElMessage.error('加载统计数据失败')
  }
}

// 获取进度条颜色
const getProgressColor = (percentage) => {
  if (percentage > 50) return '#67c23a'
  if (percentage > 20) return '#e6a23c'
  return '#f56c6c'
}

onMounted(() => {
  loadStatistics()
})
</script>

<style scoped>
.statistics-container {
  padding: 0;
  max-height: calc(100vh - 100px);
  overflow-y: auto;
  padding-right: 10px;
}

/* 滚动条样式 */
.statistics-container::-webkit-scrollbar {
  width: 8px;
}

.statistics-container::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}

.statistics-container::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 4px;
}

.statistics-container::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

.stats-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin-bottom: 20px;
}

.stats-card {
  height: 120px;
}

.stats-item {
  display: flex;
  align-items: center;
  height: 100%;
}

.stats-icon {
  font-size: 36px;
  color: #409eff;
  margin-right: 20px;
}

.stats-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.stats-label {
  font-size: 14px;
  color: #909399;
  margin-top: 5px;
}

/* 应用统计样式 */
.app-stats {
  margin-top: 20px;
}

.app-stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
}

.app-stats-card {
  min-height: 200px;
}

.app-stats-header {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
}

.app-stats-header el-icon {
  font-size: 24px;
  color: #409eff;
  margin-right: 10px;
}

.app-stats-header h4 {
  margin: 0;
  font-size: 16px;
  color: #303133;
}

.app-stats-content {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 15px;
}

.app-stats-item {
  text-align: center;
  padding: 10px;
  background-color: #f9fafc;
  border-radius: 4px;
}

.app-stats-item.pending {
  background-color: #fef0f0;
  border-left: 3px solid #f56c6c;
}

.app-stats-value {
  font-size: 20px;
  font-weight: bold;
  color: #303133;
}

.app-stats-item.pending .app-stats-value {
  color: #f56c6c;
}

.app-stats-label {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}

.app-stats-item.pending .app-stats-label {
  color: #c06c84;
}

.chart-container {
  margin-top: 20px;
}

.pie-chart {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.mb-4 {
  margin-bottom: 20px;
}

h2 {
  margin: 0 0 10px 0;
  font-size: 18px;
  color: #303133;
}

h3 {
  margin: 0 0 20px 0;
  font-size: 16px;
  color: #303133;
}

p {
  margin: 0;
  color: #909399;
  font-size: 14px;
}
</style>
