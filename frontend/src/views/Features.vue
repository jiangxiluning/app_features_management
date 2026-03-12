<template>
  <div class="features-container">
    <el-card class="mb-4">
      <div class="card-header">
        <h2>功能管理</h2>
        <el-button type="primary" @click="handleAddAppNode" v-if="isAdmin">添加应用节点</el-button>
      </div>
    </el-card>

    <div class="features-content">
      <!-- 左侧树形结构 -->
      <div class="tree-panel" :style="{ width: treeWidth + '%' }">
        <el-card class="tree-container">
          <h3>功能树</h3>
          <el-tree
            :data="featuresTree"
            node-key="id"
            :props="treeProps"
            :default-expand-all="false"
            :expand-on-click-node="false"
            :auto-expand-parent="false"
            :default-expanded-keys="expandedKeys"
            @node-click="handleNodeClick"
            @node-expand="handleNodeExpand"
            @node-collapse="handleNodeCollapse"
            @node-contextmenu="handleNodeContextMenu"
            draggable
            :allow-drop="handleAllowDrop"
            @node-drop="handleNodeDrop"
            :dragover-expression="handleDragover"
            class="feature-tree"
          >
            <template #default="{ node, data }">
              <span class="tree-node" :data-node-type="data.node_type">
                <span class="node-emoji">{{ data.node_type === 'app' ? '💻' : data.node_type === 'category' ? '📁' : '🛠️' }}</span>
                <span>{{ data.name }}</span>
                <span class="node-status status-{{ data.status }}">{{ data.status === 'pending' ? ' ❓' : '' }}</span>
              </span>
            </template>
          </el-tree>
        </el-card>
      </div>

      <!-- 分割线 -->
      <div class="splitter" @mousedown="startDrag" :style="{ left: treeWidth + '%' }"></div>

      <!-- 右侧详细信息 -->
      <div class="detail-panel" :style="{ width: 100 - treeWidth + '%' }">
        <el-card class="detail-container" v-if="selectedFeature">
          <div class="detail-header">
            <h3>{{ selectedFeature.name }} - 详细信息</h3>
            <el-button type="primary" @click="handleEditFeature(selectedFeature)" v-if="selectedFeature.status !== 'pending' && selectedFeature.node_type !== 'app'">
              编辑
            </el-button>
            <el-button type="success" @click="handleOpenVersionDialog(selectedFeature.id)" v-if="selectedFeature.node_type === 'app' && isAdmin && selectedFeature.status !== 'pending'">
              版本管理
            </el-button>
            <el-button type="danger" @click="handleDeleteFeature(selectedFeature.id)" v-if="selectedFeature.status !== 'pending'">
              删除
            </el-button>
            <el-button type="warning" @click="handleWithdrawAudit(selectedFeature.id)" v-if="selectedFeature.status === 'pending' && !isAdmin">
              撤回审核
            </el-button>
          </div>
          <div class="detail-content">
            <!-- 对于更新的节点，显示前后对比 -->
            <div v-if="selectedFeature.status === 'pending' && auditLogs.length > 0" class="audit-comparison">
              <!-- 对于新增的节点，只显示新增 -->
              <template v-if="auditLogs[0].action === 'create'">
                <h4>新增节点</h4>
                <el-card class="comparison-panel">
                  <template #header>
                    <div class="panel-header">
                      <span>新增</span>
                    </div>
                  </template>
                  <el-descriptions border size="small" column="1">
                    <el-descriptions-item :label="selectedFeature.node_type === 'app' ? '应用名称' : selectedFeature.node_type === 'category' ? '分类名称' : '功能名称'">
                      {{ selectedFeature.name }}
                    </el-descriptions-item>
                    <el-descriptions-item :label="selectedFeature.node_type === 'app' ? '应用描述' : selectedFeature.node_type === 'category' ? '分类描述' : '功能描述'">
                      <div class="description-preview" v-html="renderedTruncatedDescription" @click="handlePreviewDescriptionForPending"></div>
                    </el-descriptions-item>
                    <!-- 只有功能节点显示详细信息 -->
                    <template v-if="selectedFeature.node_type === 'function'">
                      <el-descriptions-item label="典型使用案例">
                      <div v-if="selectedFeature.use_cases">
                        <div v-if="typeof selectedFeature.use_cases === 'string' && selectedFeature.use_cases.trim()">
                          <div v-if="isValidJSON(selectedFeature.use_cases)">
                            <div v-for="(useCase, index) in parseUseCases(selectedFeature.use_cases)" :key="index" class="use-case-item-detail">
                              <div class="use-case-type" v-if="useCase.type">
                                <el-tag size="small" type="info">{{ getUseCaseTypeLabel(useCase.type) }}</el-tag>
                              </div>
                              <div class="description-preview use-case-content" v-html="marked(useCase.value)" @click="handlePreviewUseCase(useCase.value)"></div>
                              <hr v-if="index < parseUseCases(selectedFeature.use_cases).length - 1" style="margin: 10px 0; border-top: 1px dashed #e4e7ed;">
                            </div>
                          </div>
                          <div v-else>
                            <div class="description-preview" v-html="marked(selectedFeature.use_cases)" @click="handlePreviewUseCase(selectedFeature.use_cases)"></div>
                          </div>
                        </div>
                        <div v-else-if="Array.isArray(selectedFeature.use_cases)">
                          <div v-for="(useCase, index) in selectedFeature.use_cases" :key="index" class="use-case-item-detail">
                            <div class="use-case-type" v-if="useCase.type">
                              <el-tag size="small" type="info">{{ getUseCaseTypeLabel(useCase.type) }}</el-tag>
                            </div>
                            <div class="description-preview use-case-content" v-html="marked(useCase.value)" @click="handlePreviewUseCase(useCase.value)"></div>
                            <hr v-if="index < selectedFeature.use_cases.length - 1" style="margin: 10px 0; border-top: 1px dashed #e4e7ed;">
                          </div>
                        </div>
                      </div>
                      <span v-else>无</span>
                    </el-descriptions-item>
                      <el-descriptions-item label="教学视频">
                        <div v-if="selectedFeature.videos">
                          <a 
                            v-for="(video, index) in selectedFeature.videos.split(',').filter(v => v.trim())" 
                            :key="index"
                            :href="video.trim()"
                            target="_blank"
                            class="video-link"
                          >
                            视频 {{ index + 1 }}
                          </a>
                        </div>
                        <span v-else>无</span>
                      </el-descriptions-item>
                      <el-descriptions-item label="版本范围">
                        {{ selectedFeature.version_range }}
                      </el-descriptions-item>
                      <el-descriptions-item label="是否支持引导">
                        {{ (selectedFeature.is_guide_supported === true || selectedFeature.is_guide_supported === 'true') ? '是' : '否' }}
                      </el-descriptions-item>
                      <el-descriptions-item label="支持设备">
                        <div v-if="selectedFeature.devices === 'all'">所有设备</div>
                        <div v-else-if="selectedFeature.devices">
                          <el-tag v-for="deviceId in selectedFeature.devices.split(',')" :key="deviceId" size="small" style="margin-right: 5px;">
                            {{ getDeviceName(parseInt(deviceId)) }}
                          </el-tag>
                        </div>
                        <div v-else>无</div>
                      </el-descriptions-item>
                    </template>
                  </el-descriptions>
                </el-card>
              </template>
              <!-- 对于更新的节点，显示前后对比 -->
              <template v-else>
                <h4>审核对比</h4>
                <el-table :data="comparisonData" style="width: 100%" border>
                  <el-table-column prop="field" label="字段" width="180" />
                  <el-table-column prop="before" label="更新前">
                    <template #default="scope">
                      <div v-if="scope.row.field.includes('描述')" class="description-preview" v-html="scope.row.beforeHtml" @click="handlePreviewDescription(oldFeatureData.description || scope.row.before)"></div>
                      <template v-else>
                        {{ scope.row.before }}
                      </template>
                    </template>
                  </el-table-column>
                  <el-table-column prop="after" label="更新后">
                    <template #default="scope">
                      <div v-if="scope.row.field.includes('描述')" class="description-preview" v-html="scope.row.afterHtml" @click="handlePreviewDescription(selectedFeature.description || scope.row.after)"></div>
                      <template v-else>
                        {{ scope.row.after }}
                      </template>
                    </template>
                  </el-table-column>
                </el-table>
              </template>
            </div>
            <!-- 常规详情 -->
            <el-descriptions border size="small" column="1" v-else>
              <el-descriptions-item :label="selectedFeature.node_type === 'app' ? '应用名称' : selectedFeature.node_type === 'category' ? '分类名称' : '功能名称'">
                {{ selectedFeature.name }}
              </el-descriptions-item>
              <el-descriptions-item :label="selectedFeature.node_type === 'app' ? '应用描述' : selectedFeature.node_type === 'category' ? '分类描述' : '功能描述'">
                <div class="description-preview" v-html="renderedTruncatedDescription" @click="handlePreviewDescription(selectedFeature.description)"></div>
              </el-descriptions-item>
              <!-- 只有功能节点显示详细信息 -->
              <template v-if="selectedFeature.node_type === 'function'">
                <el-descriptions-item label="典型使用案例">
                  <div v-if="selectedFeature.use_cases">
                    <div v-if="typeof selectedFeature.use_cases === 'string' && selectedFeature.use_cases.trim()">
                      <div v-if="isValidJSON(selectedFeature.use_cases)">
                        <div v-for="(useCase, index) in parseUseCases(selectedFeature.use_cases)" :key="index" class="use-case-item-detail">
                          <div class="use-case-type" v-if="useCase.type">
                            <el-tag size="small" type="info">{{ getUseCaseTypeLabel(useCase.type) }}</el-tag>
                          </div>
                          <div class="description-preview use-case-content" v-html="marked(useCase.value)" @click="handlePreviewUseCase(useCase.value)"></div>
                          <hr v-if="index < parseUseCases(selectedFeature.use_cases).length - 1" style="margin: 10px 0; border-top: 1px dashed #e4e7ed;">
                        </div>
                      </div>
                      <div v-else>
                        <div class="description-preview" v-html="marked(selectedFeature.use_cases)" @click="handlePreviewUseCase(selectedFeature.use_cases)"></div>
                      </div>
                    </div>
                    <div v-else-if="Array.isArray(selectedFeature.use_cases)">
                      <div v-for="(useCase, index) in selectedFeature.use_cases" :key="index" class="use-case-item-detail">
                        <div class="use-case-type" v-if="useCase.type">
                          <el-tag size="small" type="info">{{ getUseCaseTypeLabel(useCase.type) }}</el-tag>
                        </div>
                        <div class="description-preview use-case-content" v-html="marked(useCase.value)" @click="handlePreviewUseCase(useCase.value)"></div>
                        <hr v-if="index < selectedFeature.use_cases.length - 1" style="margin: 10px 0; border-top: 1px dashed #e4e7ed;">
                      </div>
                    </div>
                  </div>
                  <span v-else>无</span>
                </el-descriptions-item>
                <el-descriptions-item label="教学视频">
                  <div v-if="selectedFeature.videos">
                    <a 
                      v-for="(video, index) in selectedFeature.videos.split(',').filter(v => v.trim())" 
                      :key="index"
                      :href="video.trim()"
                      target="_blank"
                      class="video-link"
                    >
                      视频 {{ index + 1 }}
                    </a>
                  </div>
                  <span v-else>无</span>
                </el-descriptions-item>
                <el-descriptions-item label="版本范围">
                  {{ selectedFeature.version_range || 'All' }}
                </el-descriptions-item>
                <el-descriptions-item label="是否支持引导">
                  {{ (selectedFeature.is_guide_supported === true || selectedFeature.is_guide_supported === 'true') ? '是' : '否' }}
                </el-descriptions-item>
                <el-descriptions-item label="支持设备">
                  <div v-if="selectedFeature.devices === 'all'">所有设备</div>
                  <div v-else-if="selectedFeature.devices">
                    <el-tag v-for="deviceId in selectedFeature.devices.split(',')" :key="deviceId" size="small" style="margin-right: 5px;">
                      {{ getDeviceName(parseInt(deviceId)) }}
                    </el-tag>
                  </div>
                  <div v-else>无</div>
                </el-descriptions-item>
              </template>
              <el-descriptions-item label="创建时间">
                {{ selectedFeature.created_at }}
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </el-card>
        <el-card class="detail-container" v-else>
          <div class="empty-detail">
            <el-empty description="请选择一个功能节点查看详细信息" />
          </div>
        </el-card>
      </div>
    </div>



    <!-- 右键菜单 -->
    <div
      v-if="contextMenuVisible"
      class="custom-context-menu"
      :style="{
        position: 'fixed',
        left: contextMenuPosition.x + 'px',
        top: contextMenuPosition.y + 'px',
        zIndex: 999999,
        backgroundColor: '#fff',
        border: '1px solid #dcdfe6',
        borderRadius: '4px',
        boxShadow: '0 2px 12px 0 rgba(0, 0, 0, 0.1)',
        minWidth: '150px',
        padding: '4px 0'
      }"
      @click.stop
    >
      <div class="context-menu-item" @click="handleContextMenuCommand('edit')" v-if="currentContextNode?.node_type !== 'app'">编辑</div>
      <div class="context-menu-item" @click="handleContextMenuCommand('delete')">删除</div>
      <div class="context-menu-divider" v-if="currentContextNode?.node_type !== 'app'"></div>
      <div class="context-menu-item-header" v-if="currentContextNode?.node_type !== 'app'">移动</div>
      <div class="context-menu-item" @click="handleContextMenuCommand('moveTop')" v-if="currentContextNode?.node_type === 'function'">移动到顶层</div>
      <div class="context-menu-item" @click="handleContextMenuCommand('moveCustom')" v-if="currentContextNode?.node_type !== 'app'">自定义移动</div>
      <div class="context-menu-divider" v-if="currentContextNode?.status === 'pending' && isAdmin"></div>
      <div class="context-menu-item-header" v-if="currentContextNode?.status === 'pending' && isAdmin">审核</div>
      <div class="context-menu-item" @click="handleContextMenuCommand('approve')" v-if="currentContextNode?.status === 'pending' && isAdmin">审核通过</div>
      <div class="context-menu-divider" v-if="currentContextNode?.node_type === 'app' && canExport"></div>
      <div class="context-menu-item" @click="handleContextMenuCommand('export')" v-if="currentContextNode?.node_type === 'app' && canExport">导出</div>
      <div class="context-menu-divider" v-if="currentContextNode?.node_type === 'app' && isAdmin"></div>
      <div class="context-menu-item-header" v-if="currentContextNode?.node_type === 'app' && isAdmin">版本管理</div>
      <div class="context-menu-item" @click="handleContextMenuCommand('manageVersions')" v-if="currentContextNode?.node_type === 'app' && isAdmin">管理版本</div>
      <div class="context-menu-divider" v-if="(currentContextNode?.node_type === 'app' || currentContextNode?.node_type === 'category')"></div>
      <div class="context-menu-item-header" v-if="currentContextNode?.node_type === 'app' || currentContextNode?.node_type === 'category'">添加</div>
      <div class="context-menu-item" @click="handleContextMenuCommand('addCategory')" v-if="currentContextNode?.node_type === 'app' || currentContextNode?.node_type === 'category'">添加分类</div>
      <div class="context-menu-item" @click="handleContextMenuCommand('addFunction')" v-if="currentContextNode?.node_type === 'app' || currentContextNode?.node_type === 'category'">添加功能</div>
    </div>

    <!-- 编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="700px"
    >
      <el-form
        ref="featureFormRef"
        :model="featureForm"
        :rules="rules"
        label-width="120px"
      >
        <el-form-item label="节点类型" prop="node_type">
          <el-select v-model="featureForm.node_type" disabled>
            <el-option label="应用" value="app"></el-option>
            <el-option label="分类" value="category"></el-option>
            <el-option label="功能" value="function"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item :label="featureForm.node_type === 'app' ? '应用名称' : featureForm.node_type === 'category' ? '分类名称' : '功能名称'" prop="name">
          <el-input v-model="featureForm.name"></el-input>
        </el-form-item>
        <el-form-item :label="featureForm.node_type === 'app' ? '应用描述' : featureForm.node_type === 'category' ? '分类描述' : '功能描述'" prop="description">
          <el-tabs v-model="activeTab">
            <el-tab-pane label="编辑" name="edit">
              <el-input
                type="textarea"
                v-model="featureForm.description"
                :rows="10"
                placeholder="请输入功能描述（支持 Markdown 格式）"
              ></el-input>
            </el-tab-pane>
            <el-tab-pane label="预览" name="preview">
              <div class="markdown-preview" v-html="renderedPreviewDescription"></div>
            </el-tab-pane>
          </el-tabs>
        </el-form-item>
        <el-form-item v-if="featureForm.node_type === 'function'" label="典型使用案例">
          <el-tabs v-model="activeUseCaseTab">
            <el-tab-pane label="编辑" name="edit">
              <div>
                <div v-for="(item, index) in useCasesList" :key="index" class="use-case-item">
                  <el-input
                    type="textarea"
                    v-model="item.value"
                    :rows="4"
                    placeholder="请输入使用案例"
                    style="margin-bottom: 10px"
                  ></el-input>
                  <el-row :gutter="10" style="width: 100%">
                    <el-col :span="12">
                      <el-button
                        type="danger"
                        size="small"
                        @click="removeUseCase(index)"
                        :disabled="useCasesList.length <= 1"
                        style="width: 100%"
                      >
                        删除
                      </el-button>
                    </el-col>
                    <el-col :span="12">
                      <el-button
                        type="primary"
                        size="small"
                        @click="addUseCase"
                        style="width: 100%"
                      >
                        添加
                      </el-button>
                    </el-col>
                  </el-row>
                </div>
              </div>
            </el-tab-pane>
            <el-tab-pane label="预览" name="preview">
              <div class="markdown-preview" v-html="renderedUseCasePreview"></div>
            </el-tab-pane>
          </el-tabs>
        </el-form-item>
        <el-form-item v-if="featureForm.node_type === 'function'" label="教学视频">
          <div>
            <div v-for="(item, index) in videosList" :key="index" class="video-item">
              <el-row :gutter="10" style="width: 100%">
                <el-col :span="16">
                  <el-input
                    v-model="item.value"
                    placeholder="请输入视频 URL"
                  ></el-input>
                </el-col>
                <el-col :span="4">
                  <el-button
                    type="danger"
                    size="small"
                    @click="removeVideo(index)"
                    :disabled="videosList.length <= 1"
                    style="width: 100%"
                  >
                    删除
                  </el-button>
                </el-col>
                <el-col :span="4">
                  <el-button
                    type="primary"
                    size="small"
                    @click="addVideo"
                    style="width: 100%"
                  >
                    添加
                  </el-button>
                </el-col>
              </el-row>
            </div>
          </div>
        </el-form-item>
        <el-form-item v-if="featureForm.node_type === 'function'" label="版本范围" prop="version_range" style="align-items: center;">
          <el-row :gutter="20" style="align-items: center; width: 100%;">
            <el-col :span="16">
              <el-tag v-if="featureForm.version_range" type="info" style="width: 100%; text-align: center; padding: 10px; font-size: 14px; height: 32px; display: flex; align-items: center; justify-content: center;">
                {{ featureForm.version_range }}
              </el-tag>
              <el-tag v-else type="warning" style="width: 100%; text-align: center; padding: 10px; font-size: 14px; height: 32px; display: flex; align-items: center; justify-content: center;">
                请选择版本范围
              </el-tag>
            </el-col>
            <el-col :span="8">
              <el-button
                type="primary"
                @click="handleOpenVersionRangeDialog"
                style="width: auto; min-width: 100px;"
              >
                选择版本范围
              </el-button>
            </el-col>
          </el-row>
        </el-form-item>
        <el-form-item v-if="featureForm.node_type === 'function'" label="是否支持引导" prop="is_guide_supported">
          <el-checkbox v-model="featureForm.is_guide_supported"></el-checkbox>
        </el-form-item>
        <el-form-item v-if="featureForm.node_type === 'function'" label="支持设备" prop="devices">
          <el-checkbox v-model="selectAllDevices" @change="handleSelectAllDevices">所有设备</el-checkbox>
          <el-select
            v-model="selectedDevices"
            multiple
            placeholder="请选择支持的设备"
            style="width: 100%; margin-top: 10px"
            :disabled="selectAllDevices"
          >
            <el-option
              v-for="device in availableDevices"
              :key="device.id"
              :label="device.release_name"
              :value="device.id"
            ></el-option>
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveFeature">确定</el-button>
      </template>
    </el-dialog>

    <!-- 预览对话框 -->
    <el-dialog
      v-model="previewDialogVisible"
      title="描述预览"
      width="800px"
    >
      <div class="markdown-full-preview" v-html="fullRenderedDescription"></div>
      <template #footer>
        <el-button @click="previewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 移动对话框 -->
    <el-dialog
      v-model="moveDialogVisible"
      title="移动节点"
      width="500px"
    >
      <el-form
        ref="moveFormRef"
        :model="moveForm"
        label-width="100px"
      >
        <el-form-item label="当前节点">
          <el-input v-model="moveForm.currentNodeName" disabled></el-input>
        </el-form-item>
        <el-form-item label="新父节点">
          <el-select v-model="moveForm.newParentId" placeholder="请选择新父节点">
            <el-option label="顶层" value=""></el-option>
            <el-option
              v-for="node in availableParentNodes"
              :key="node.id"
              :label="node.name"
              :value="node.id"
            ></el-option>
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="moveDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleConfirmMove">确定</el-button>
      </template>
    </el-dialog>

    <!-- 移动确认对话框 -->
    <el-dialog
      v-model="moveConfirmVisible"
      title="确认移动"
      width="500px"
    >
      <div class="move-confirm-content">
        <p>您确定要将节点 <strong>{{ moveConfirmData.sourceName }}</strong> 移动到 <strong>{{ moveConfirmData.targetName }}</strong> 吗？</p>
        <el-checkbox v-model="moveConfirmData.dontRemindAgain">不再提醒</el-checkbox>
      </div>
      <template #footer>
        <el-button @click="handleCancelMove">取消</el-button>
        <el-button type="primary" @click="handleMoveConfirmOk">确定</el-button>
      </template>
    </el-dialog>

    <!-- 版本管理对话框 -->
    <el-dialog
      v-model="versionDialogVisible"
      title="版本管理"
      width="600px"
    >
      <el-form
        ref="versionFormRef"
        :model="versionForm"
        :rules="versionRules"
        label-width="100px"
      >
        <el-form-item label="版本号" prop="version" required>
          <el-row :gutter="5" type="flex" align="middle">
            <el-col :span="5">
              <el-input
                v-model="versionForm.major"
                type="number"
                placeholder="主版本"
                :min="0"
                :max="99999999"
                @input="handleVersionInput"
              ></el-input>
            </el-col>
            <el-col :span="1" style="text-align: center;">
              .
            </el-col>
            <el-col :span="5">
              <el-input
                v-model="versionForm.minor"
                type="number"
                placeholder="次版本"
                :min="0"
                :max="99999999"
                @input="handleVersionInput"
              ></el-input>
            </el-col>
            <el-col :span="1" style="text-align: center;">
              .
            </el-col>
            <el-col :span="5">
              <el-input
                v-model="versionForm.revision"
                type="number"
                placeholder="修订号"
                :min="0"
                :max="99999999"
                @input="handleVersionInput"
              ></el-input>
            </el-col>
            <el-col :span="1" style="text-align: center;">
              .
            </el-col>
            <el-col :span="5">
              <el-input
                v-model="versionForm.build"
                type="number"
                placeholder="构建号"
                :min="0"
                :max="99999999"
                @input="handleVersionInput"
              ></el-input>
            </el-col>
          </el-row>
        </el-form-item>
        <el-form-item label="更新日志">
          <el-input
            type="textarea"
            v-model="versionForm.changelog"
            :rows="5"
            placeholder="请输入更新日志（支持 Markdown 格式）"
          ></el-input>
        </el-form-item>
      </el-form>
      <div class="version-list">
        <h4>版本列表</h4>
        <el-table :data="appVersions" style="width: 100%">
          <el-table-column prop="version" label="版本号" width="120"></el-table-column>
          <el-table-column prop="changelog" label="更新日志">
            <template #default="scope">
              <div class="changelog-preview" v-html="marked(scope.row.changelog || '')"></div>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="180"></el-table-column>
          <el-table-column label="操作" width="100">
            <template #default="scope">
              <el-button type="danger" size="small" @click="handleDeleteVersion(scope.row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <template #footer>
        <el-button @click="versionDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="handleAddVersion">添加版本</el-button>
      </template>
    </el-dialog>

    <!-- 版本范围选择对话框 -->
    <el-dialog
      v-model="versionRangeDialogVisible"
      title="选择版本范围"
      width="500px"
    >
      <el-form
        ref="versionRangeFormRef"
        :model="versionRangeForm"
        :rules="versionRangeRules"
        label-width="100px"
      >
        <el-form-item label="范围类型" prop="rangeType">
          <el-select v-model="versionRangeForm.rangeType">
            <el-option label=">= 版本号" value=">="></el-option>
            <el-option label="<= 版本号" value="<="></el-option>
            <el-option label="版本范围" value="-"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="起始版本" prop="startVersion">
          <el-select v-model="versionRangeForm.startVersion" placeholder="请选择起始版本">
            <el-option
              v-for="version in availableVersions"
              :key="version.id"
              :label="version.version"
              :value="version.version"
            ></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="结束版本" prop="endVersion">
          <el-select v-model="versionRangeForm.endVersion" placeholder="请选择结束版本" v-if="versionRangeForm.rangeType === '-'">
            <el-option
              v-for="version in availableVersions"
              :key="version.id"
              :label="version.version"
              :value="version.version"
            ></el-option>
          </el-select>
          <el-input v-model="versionRangeForm.endVersion" disabled v-else></el-input>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="versionRangeDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleConfirmVersionRange">确定</el-button>
      </template>
    </el-dialog>

    <!-- 导出对话框 -->
    <el-dialog
      v-model="exportDialogVisible"
      title="导出功能为Markdown"
      width="80%"
      :before-close="handleClose"
    >
      <div style="padding: 20px; min-height: 600px;">
        <!-- 模板说明超链接 -->
        <div style="margin-bottom: 20px;">
          <el-link type="primary" @click="showTemplateHelp = true">查看模板字符串语义解释</el-link>
        </div>
        
        <!-- 导出模板编辑框 -->
        <div style="margin-bottom: 20px;">
          <label style="display: block; margin-bottom: 10px; font-weight: bold;">导出模板</label>
          <textarea
            v-model="exportTemplate"
            style="width: 100%; height: 400px; padding: 10px; border: 1px solid #dcdfe6; border-radius: 4px; resize: vertical; font-family: monospace;"
            placeholder="使用{{字段名}}的形式插入字段值，例如{{name}}、{{description}}等"
          ></textarea>
        </div>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="exportDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmExport" :loading="isExporting">
            导出
          </el-button>
        </span>
      </template>
    </el-dialog>
    
    <!-- 模板字符串语义解释对话框 -->
    <el-dialog
      v-model="showTemplateHelp"
      title="模板字符串语义解释"
      width="60%"
    >
      <el-table :data="templateSemantics" style="width: 100%">
        <el-table-column prop="template" label="模板字符串" width="180" />
        <el-table-column prop="semantic" label="语义解释" />
      </el-table>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showTemplateHelp = false">关闭</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>



<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, h, nextTick } from 'vue'
import { featureAPI, versionAPI, deviceAPI } from '../api'
import api from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Minus } from '@element-plus/icons-vue'
import { marked } from 'marked'

const features = ref([])
const featuresTree = ref([])
const selectedFeature = ref(null)
const auditLogs = ref([])
const oldFeatureData = ref({})

// 检查用户角色
const isAdmin = computed(() => {
  try {
    return typeof localStorage !== 'undefined' && localStorage.getItem('role') === 'admin'
  } catch (error) {
    return false
  }
})

// 检查是否为开发者
const isDeveloper = computed(() => {
  try {
    return typeof localStorage !== 'undefined' && localStorage.getItem('role') === 'developer'
  } catch (error) {
    return false
  }
})

// 检查是否有权限使用导出功能
const canExport = computed(() => {
  return isAdmin.value || isDeveloper.value
})

// 分割线相关
const treeWidth = ref(30)
const isDragging = ref(false)

// 展开的节点ID数组
const expandedKeys = ref([])

// 对话框相关
const dialogVisible = ref(false)
const dialogTitle = ref('添加功能')
const featureFormRef = ref(null)
const activeTab = ref('edit')
const activeUseCaseTab = ref('edit')
const previewDialogVisible = ref(false)
const previewDescription = ref('')
const moveDialogVisible = ref(false)
const moveFormRef = ref(null)
const moveForm = reactive({
  currentNodeId: '',
  currentNodeName: '',
  newParentId: null
})
const availableParentNodes = ref([])
// 菜单状态管理
const currentOpenMenu = ref(null)
// 右键菜单相关
const contextMenuVisible = ref(false)
const contextMenuPosition = reactive({ x: 0, y: 0 })
const currentContextNode = ref(null)

// 导出相关
const exportDialogVisible = ref(false)
const showTemplateHelp = ref(false)
const templateSemantics = ref([
  { template: '{{name}}', semantic: '功能名称' },
  { template: '{{description}}', semantic: '功能描述' },
  { template: '{{#use_cases}}...{{/use_cases}}', semantic: '典型使用案例列表' },
  { template: '{{index}}', semantic: '列表项索引' },
  { template: '{{index + 1}}', semantic: '列表项索引+1' },
  { template: '{{value}}', semantic: '列表项值' },
  { template: '{{#videos}}...{{/videos}}', semantic: '教学视频列表' },
  { template: '{{url}}', semantic: '视频链接' },
  { template: '{{version_range}}', semantic: '版本范围' },
  { template: '{{is_guide_supported}}', semantic: '是否支持引导' },
  { template: '{{#devices}}...{{/devices}}', semantic: '支持设备列表' },
  { template: '{{device_name}}', semantic: '设备名称' }
])
const exportTemplate = ref(`# 功能名称
{{name}}

# 功能描述
{{description}}

# 典型使用案例
{{#use_cases}}
## 案例 {{index + 1}}
{{value}}
{{/use_cases}}

# 教学视频
{{#videos}}
## 视频 {{index + 1}}
{{url}}
{{/videos}}

# 版本范围
{{version_range}}

# 是否支持引导
{{is_guide_supported}}

# 支持设备
{{#devices}}
{{device_name}}
{{/devices}}`)
const isExporting = ref(false)
// 移动确认对话框
const moveConfirmVisible = ref(false)
const moveConfirmData = reactive({
  sourceId: '',
  sourceName: '',
  targetId: '',
  targetName: '',
  dontRemindAgain: false,
  moveType: ''
})
// 本地存储，记录用户是否选择了不再提醒
const getDontRemindAgain = () => {
  try {
    return typeof localStorage !== 'undefined' && localStorage.getItem('moveDontRemindAgain') === 'true'
  } catch (error) {
    return false
  }
}
const setDontRemindAgain = (value) => {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('moveDontRemindAgain', value)
    }
  } catch (error) {
    console.error('Error setting localStorage:', error)
  }
}
const featureForm = reactive({
  id: '',
  name: '',
  description: '',
  use_cases: '',
  videos: '',
  version_range: '>= 0.0.0.0',
  parent_id: null,
  node_type: 'function',
  is_guide_supported: false
})

// 版本管理相关
const versionDialogVisible = ref(false)
const versionFormRef = ref(null)
const versionForm = reactive({
  version: '',
  major: '',
  minor: '',
  revision: '',
  build: '',
  changelog: ''
})
const versionRules = {
  version: [{ required: true, message: '请输入版本号', trigger: 'blur' }]
}

// 处理版本输入
const handleVersionInput = () => {
  // 确保每个字段都是数字且不为空
  const major = parseInt(versionForm.major) || 0
  const minor = parseInt(versionForm.minor) || 0
  const revision = parseInt(versionForm.revision) || 0
  const build = parseInt(versionForm.build) || 0
  
  // 限制最大值为99999999
  const clampedMajor = Math.min(major, 99999999)
  const clampedMinor = Math.min(minor, 99999999)
  const clampedRevision = Math.min(revision, 99999999)
  const clampedBuild = Math.min(build, 99999999)
  
  // 更新表单值
  versionForm.major = clampedMajor.toString()
  versionForm.minor = clampedMinor.toString()
  versionForm.revision = clampedRevision.toString()
  versionForm.build = clampedBuild.toString()
  
  // 更新版本号
  versionForm.version = `${clampedMajor}.${clampedMinor}.${clampedRevision}.${clampedBuild}`
}
const appVersions = ref([])
const currentAppId = ref(null)

// 版本范围选择相关
const versionRangeDialogVisible = ref(false)
const versionRangeFormRef = ref(null)
const versionRangeForm = reactive({
  rangeType: '>=',
  startVersion: '',
  endVersion: ''
})
const versionRangeRules = {
  rangeType: [{ required: true, message: '请选择范围类型', trigger: 'blur' }],
  startVersion: [{ required: true, message: '请选择起始版本', trigger: 'blur' }],
  endVersion: [
    {
      required: true,
      message: '请选择结束版本',
      trigger: 'blur',
      validator: (rule, value, callback) => {
        if (versionRangeForm.rangeType === '-' && !value) {
          callback(new Error('请选择结束版本'))
        } else {
          callback()
        }
      }
    }
  ]
}
const availableVersions = ref([])

// 设备相关
const availableDevices = ref([])
const selectedDevices = ref([])
const selectAllDevices = ref(false)

// 动态字段数组
const useCasesList = ref([])
const videosList = ref([])



// Markdown预览相关
const renderedDescription = ref('')
const renderedPreviewDescription = computed(() => {
  return marked(featureForm.description || '')
})
const fullRenderedDescription = computed(() => {
  return marked(previewDescription.value || '')
})
const renderedUseCasePreview = computed(() => {
  const useCaseContent = useCasesList.value
    .filter(item => item.value)
    .map((item, index) => {
      return `## 使用案例 ${index + 1}\n${item.value}`
    })
    .join('\n\n')
  return marked(useCaseContent || '')
})

const rules = {
  name: [{ required: true, message: '请输入功能名称', trigger: 'blur' }],
  description: [{ required: true, message: '请输入功能描述', trigger: 'blur' }],
  version_range: [{ required: true, message: '请输入版本范围', trigger: 'blur', 
    validator: (rule, value, callback) => {
      if (featureForm.node_type === 'function' && !value) {
        callback(new Error('请输入版本范围'))
      } else {
        callback()
      }
    }
  }],
  is_guide_supported: [{ required: true, message: '请选择是否支持引导', trigger: 'change',
    validator: (rule, value, callback) => {
      if (featureForm.node_type === 'function' && value === undefined) {
        callback(new Error('请选择是否支持引导'))
      } else {
        callback()
      }
    }
  }],
  devices: [{ required: true, message: '请选择支持设备', trigger: 'change',
    validator: (rule, value, callback) => {
      if (featureForm.node_type === 'function' && !value && selectedDevices.value.length === 0 && !selectAllDevices.value) {
        callback(new Error('请选择支持设备'))
      } else {
        callback()
      }
    }
  }]
}

// 树形结构配置
const treeProps = {
  children: 'children',
  label: 'name'
}

// 加载设备列表
const loadDevices = async () => {
  try {
    const response = await deviceAPI.getDevices()
    availableDevices.value = response.data
  } catch (error) {
    console.error('加载设备列表失败:', error)
  }
}

// 处理选择所有设备
const handleSelectAllDevices = (value) => {
  if (value) {
    selectedDevices.value = []
  }
}

// 加载数据
const loadData = async () => {
  try {
    let username = 'user'
    let userRole = 'developer'
    let user_id = '1'
    try {
      username = localStorage.getItem('username') || 'user'
      userRole = localStorage.getItem('role') || 'developer'
      user_id = localStorage.getItem('user_id') || '1'
    } catch (error) {
      console.error('Error getting localStorage:', error)
    }
    
    const featuresResponse = await featureAPI.getFeatures(userRole, user_id)
    // 后端返回的响应包含data和total字段
    featuresTree.value = featuresResponse.data.data
    
    // 加载设备列表
    await loadDevices()
    
    // 使用nextTick确保树组件在数据更新后能够正确地应用展开状态
    await nextTick()
  } catch (error) {
    ElMessage.error('加载数据失败')
  }
}

// 截断描述内容（只显示前5行）
const truncateDescription = (description) => {
  if (!description) return ''
  const lines = description.split('\n')
  if (lines.length <= 5) return description
  return lines.slice(0, 5).join('\n') + '\n...'
}

// 渲染旧描述（Markdown）
const renderOldDescription = computed(() => {
  if (!oldFeatureData.value.description) return ''
  return marked(truncateDescription(oldFeatureData.value.description || ''))
})

// 渲染截断的当前描述
const renderedTruncatedDescription = computed(() => {
  return marked(truncateDescription(selectedFeature.value.description || ''))
})

// 生成对比表格数据
const comparisonData = computed(() => {
  const data = []
  const nodeType = oldFeatureData.value.node_type || selectedFeature.value.node_type
  
  // 添加名称字段
  data.push({
    field: nodeType === 'app' ? '应用名称' : nodeType === 'category' ? '分类名称' : '功能名称',
    before: oldFeatureData.value.name || selectedFeature.value.name,
    after: selectedFeature.value.name
  })
  
  // 添加描述字段
  data.push({
    field: nodeType === 'app' ? '应用描述' : nodeType === 'category' ? '分类描述' : '功能描述',
    before: oldFeatureData.value.description || '',
    after: selectedFeature.value.description || '',
    beforeHtml: marked(truncateDescription(oldFeatureData.value.description || '')),
    afterHtml: marked(truncateDescription(selectedFeature.value.description || ''))
  })
  
  // 只有功能节点显示详细信息
  if (nodeType === 'function') {
    // 添加典型使用案例字段
    data.push({
      field: '典型使用案例',
      before: oldFeatureData.value.use_cases || '无',
      after: selectedFeature.value.use_cases || '无'
    })
    
    // 添加教学视频字段
    data.push({
      field: '教学视频',
      before: oldFeatureData.value.videos || '无',
      after: selectedFeature.value.videos || '无'
    })
    
    // 添加版本范围字段
    data.push({
      field: '版本范围',
      before: oldFeatureData.value.version_range || 'All',
      after: selectedFeature.value.version_range || 'All'
    })
    
    // 添加是否支持引导字段
    data.push({
      field: '是否支持引导',
      before: (oldFeatureData.value.is_guide_supported === true || oldFeatureData.value.is_guide_supported === 'true') ? '是' : '否',
      after: (selectedFeature.value.is_guide_supported === true || selectedFeature.value.is_guide_supported === 'true') ? '是' : '否'
    })
    
    // 添加支持设备字段
    data.push({
      field: '支持设备',
      before: oldFeatureData.value.devices === 'all' ? '所有设备' : formatDeviceList(oldFeatureData.value.devices),
      after: selectedFeature.value.devices === 'all' ? '所有设备' : formatDeviceList(selectedFeature.value.devices)
    })
  }
  
  return data
})

// 从审核记录中获取描述内容
const getDescriptionFromAuditLogs = () => {
  if (auditLogs.value.length > 0) {
    const audit = auditLogs.value[0]
    if (audit.action === 'create' && audit.after_content) {
      try {
        // 尝试解析JSON格式
        const afterContent = JSON.parse(audit.after_content)
        return afterContent.description || ''
      } catch (error) {
        try {
          // 尝试处理Python格式的字典字符串
          const cleanedContent = audit.after_content
            .replace(/'/g, '"')  // 将单引号替换为双引号
            .replace(/None/g, 'null')  // 将None替换为null
            .replace(/True/g, 'true')  // 将True替换为true
            .replace(/False/g, 'false')  // 将False替换为false
          const afterContent = JSON.parse(cleanedContent)
          return afterContent.description || ''
        } catch (error) {
          return ''
        }
      }
    } else if (audit.action === 'update' && audit.after_content) {
      try {
        // 尝试解析JSON格式
        const afterContent = JSON.parse(audit.after_content)
        return afterContent.description || ''
      } catch (error) {
        try {
          // 尝试处理Python格式的字典字符串
          const cleanedContent = audit.after_content
            .replace(/'/g, '"')  // 将单引号替换为双引号
            .replace(/None/g, 'null')  // 将None替换为null
            .replace(/True/g, 'true')  // 将True替换为true
            .replace(/False/g, 'false')  // 将False替换为false
          const afterContent = JSON.parse(cleanedContent)
          return afterContent.description || ''
        } catch (error) {
          return ''
        }
      }
    }
  }
  return ''
}

// 处理待审核节点的描述预览
const handlePreviewDescriptionForPending = () => {
  let description = selectedFeature.value.description
  if (!description && auditLogs.value.length > 0) {
    // 从审核记录中获取完整的描述内容
    const audit = auditLogs.value[0]
    if (audit.action === 'create' && audit.after_content) {
      try {
        const afterContent = JSON.parse(audit.after_content)
        description = afterContent.description || ''
      } catch (error) {
        try {
          const cleanedContent = audit.after_content
            .replace(/'/g, '"')
            .replace(/None/g, 'null')
            .replace(/True/g, 'true')
            .replace(/False/g, 'false')
          const afterContent = JSON.parse(cleanedContent)
          description = afterContent.description || ''
        } catch (error) {
          description = ''
        }
      }
    } else if (audit.action === 'update' && audit.after_content) {
      try {
        const afterContent = JSON.parse(audit.after_content)
        description = afterContent.description || ''
      } catch (error) {
        try {
          const cleanedContent = audit.after_content
            .replace(/'/g, '"')
            .replace(/None/g, 'null')
            .replace(/True/g, 'true')
            .replace(/False/g, 'false')
          const afterContent = JSON.parse(cleanedContent)
          description = afterContent.description || ''
        } catch (error) {
          description = ''
        }
      }
    }
  }
  handlePreviewDescription(description)
}

// 处理节点点击
const handleNodeClick = async (data) => {
  selectedFeature.value = data
  // 更新描述预览
  renderedDescription.value = marked(data.description || '')
  // 加载审核记录
  if (data.status === 'pending') {
    try {
      // 从API获取审核记录
      const auditResponse = await featureAPI.getAuditLogs(data.id)
      if (auditResponse.data && auditResponse.data.length > 0) {
        auditLogs.value = auditResponse.data
        // 解析旧数据
        if (auditLogs.value[0].before_content) {
          try {
            // 尝试解析JSON格式
            oldFeatureData.value = JSON.parse(auditLogs.value[0].before_content)
          } catch (error) {
            try {
              // 尝试处理Python格式的字典字符串
              const cleanedContent = auditLogs.value[0].before_content
                .replace(/'/g, '"')  // 将单引号替换为双引号
                .replace(/None/g, 'null')  // 将None替换为null
                .replace(/True/g, 'true')  // 将True替换为true
                .replace(/False/g, 'false')  // 将False替换为false
              oldFeatureData.value = JSON.parse(cleanedContent)
            } catch (error) {
              oldFeatureData.value = {}
            }
          }
        } else {
          oldFeatureData.value = {}
        }
        // 对于待审核节点，从审核记录中获取描述
        if (auditLogs.value[0].action === 'create' && auditLogs.value[0].after_content) {
          try {
            // 尝试解析JSON格式
            const afterContent = JSON.parse(auditLogs.value[0].after_content)
            if (afterContent.description) {
              renderedDescription.value = marked(afterContent.description || '')
            }
          } catch (error) {
            try {
              // 尝试处理Python格式的字典字符串
              const cleanedContent = auditLogs.value[0].after_content
                .replace(/'/g, '"')  // 将单引号替换为双引号
                .replace(/None/g, 'null')  // 将None替换为null
                .replace(/True/g, 'true')  // 将True替换为true
                .replace(/False/g, 'false')  // 将False替换为false
              const afterContent = JSON.parse(cleanedContent)
              if (afterContent.description) {
                renderedDescription.value = marked(afterContent.description || '')
              }
            } catch (error) {
              console.error('解析审核记录内容失败:', error)
            }
          }
        }
      } else {
        // 如果没有审核记录，使用默认值
        auditLogs.value = []
        oldFeatureData.value = {}
      }
    } catch (error) {
      console.error('加载审核记录失败:', error)
      auditLogs.value = []
      oldFeatureData.value = {}
    }
  } else {
    auditLogs.value = []
    oldFeatureData.value = {}
  }
}

// 节点展开事件
const handleNodeExpand = (node) => {
  if (node && node.data && node.data.id) {
    if (!expandedKeys.value.includes(node.data.id)) {
      expandedKeys.value.push(node.data.id)
    }
  }
}

// 节点折叠事件
const handleNodeCollapse = (node) => {
  if (node && node.data && node.data.id) {
    const index = expandedKeys.value.indexOf(node.data.id)
    if (index > -1) {
      expandedKeys.value.splice(index, 1)
    }
  }
}

// 处理描述预览
const handlePreviewDescription = (description) => {
  previewDescription.value = description
  previewDialogVisible.value = true
}

// 处理使用案例预览
const handlePreviewUseCase = (useCaseContent) => {
  previewDescription.value = useCaseContent
  previewDialogVisible.value = true
}

// 获取节点所属的应用根节点
const getAppRoot = (nodeId) => {
  if (!nodeId) return null
  
  const findNode = (nodes, id) => {
    for (const node of nodes) {
      if (node && node.id === id) {
        return node
      }
      if (node && node.children && node.children.length > 0) {
        const found = findNode(node.children, id)
        if (found) {
          return found
        }
      }
    }
    return null
  }
  
  const node = findNode(featuresTree.value, nodeId)
  if (!node) return null
  
  let current = node
  while (current && current.parent_id) {
    const parentNode = findNode(featuresTree.value, current.parent_id)
    if (parentNode) {
      current = parentNode
    } else {
      break
    }
  }
  return current
}

// 获取可用的父节点列表
const getAvailableParentNodes = (currentNodeId) => {
  const allNodes = []
  const currentAppRoot = getAppRoot(currentNodeId)
  
  const collectNodes = (nodes) => {
    if (!nodes || !Array.isArray(nodes)) return
    
    nodes.forEach(node => {
      if (node && node.id !== currentNodeId && node.node_type !== 'function') {
        const nodeAppRoot = getAppRoot(node.id)
        if (currentAppRoot && nodeAppRoot) {
          if (currentAppRoot.id === nodeAppRoot.id) {
            allNodes.push(node)
          }
        } else {
          allNodes.push(node)
        }
      }
      if (node && node.children && node.children.length > 0) {
        collectNodes(node.children)
      }
    })
  }
  
  collectNodes(featuresTree.value)
  return allNodes
}

// 打开移动节点对话框
const handleOpenMoveDialog = (nodeId) => {
  if (!nodeId) return
  
  const findNode = (nodes, id) => {
    if (!nodes || !Array.isArray(nodes)) return null
    
    for (const node of nodes) {
      if (node && node.id === id) {
        return node
      }
      if (node && node.children && node.children.length > 0) {
        const found = findNode(node.children, id)
        if (found) {
          return found
        }
      }
    }
    return null
  }
  
  const currentNode = findNode(featuresTree.value, nodeId)
  if (currentNode) {
    moveForm.currentNodeId = nodeId
    moveForm.currentNodeName = currentNode.name
    moveForm.newParentId = currentNode.parent_id
    availableParentNodes.value = getAvailableParentNodes(nodeId)
    moveDialogVisible.value = true
  }
}

// 处理移动节点
const handleMoveNode = async (nodeId, command) => {
  if (command === null) {
    try {
      if (!nodeId) return
      
      const findNode = (nodes, id) => {
        if (!nodes || !Array.isArray(nodes)) return null
        
        for (const node of nodes) {
          if (node && node.id === id) {
            return node
          }
          if (node && node.children && node.children.length > 0) {
            const found = findNode(node.children, id)
            if (found) {
              return found
            }
          }
        }
        return null
      }
      
      const currentNode = findNode(featuresTree.value, nodeId)
      if (!currentNode) return
      
      if (getDontRemindAgain()) {
        await featureAPI.moveFeature(nodeId, null)
        ElMessage.success('节点移动成功')
        loadData()
      } else {
        moveConfirmData.sourceId = nodeId
        moveConfirmData.sourceName = currentNode.name
        moveConfirmData.targetId = null
        moveConfirmData.targetName = '顶层'
        moveConfirmData.dontRemindAgain = false
        moveConfirmData.moveType = 'menu'
        moveConfirmVisible.value = true
      }
    } catch (error) {
      if (error.response && error.response.status === 400) {
        ElMessage.error('移动失败：' + (error.response.data.message || '目标层级已存在同名节点'))
      } else {
        ElMessage.error('移动失败：' + (error.response?.data?.message || '未知错误'))
      }
    }
  }
}

// 确认移动节点
const handleConfirmMove = async () => {
  try {
    let targetName = '顶层'
    if (moveForm.newParentId) {
      const findNode = (nodes, id) => {
        for (const node of nodes) {
          if (node.id === id) {
            return node
          }
          if (node.children && node.children.length > 0) {
            const found = findNode(node.children, id)
            if (found) {
              return found
            }
          }
        }
        return null
      }
      
      const targetNode = findNode(featuresTree.value, moveForm.newParentId)
      if (targetNode) {
        targetName = targetNode.name
      }
    }
    
    if (getDontRemindAgain()) {
      await featureAPI.moveFeature(moveForm.currentNodeId, moveForm.newParentId)
      ElMessage.success('节点移动成功')
      moveDialogVisible.value = false
      loadData()
    } else {
      moveConfirmData.sourceId = moveForm.currentNodeId
      moveConfirmData.sourceName = moveForm.currentNodeName
      moveConfirmData.targetId = moveForm.newParentId
      moveConfirmData.targetName = targetName
      moveConfirmData.dontRemindAgain = false
      moveConfirmData.moveType = 'menu'
      moveConfirmVisible.value = true
      moveDialogVisible.value = false
    }
  } catch (error) {
    if (error.response && error.response.status === 400) {
      ElMessage.error('移动失败：' + (error.response.data.message || '目标层级已存在同名节点'))
    } else {
      ElMessage.error('移动失败：' + (error.response?.data?.message || '未知错误'))
    }
  }
}



// 处理右键菜单显示/隐藏
const handleContextMenuVisibleChange = (visible, nodeId) => {
  if (visible) {
    currentOpenMenu.value = nodeId
  } else {
    if (currentOpenMenu.value === nodeId) {
      currentOpenMenu.value = null
    }
  }
}

// 处理树节点右键菜单
const handleNodeContextMenu = (event, data, node) => {
  console.log('Right click event triggered:', event)
  console.log('Current node:', data)
  event.preventDefault()
  // 设置右键菜单位置
  contextMenuPosition.x = event.clientX
  contextMenuPosition.y = event.clientY
  // 设置当前右键点击的节点
  currentContextNode.value = data
  // 显示右键菜单
  contextMenuVisible.value = true
  console.log('Context menu visible:', contextMenuVisible.value)
  console.log('Context menu position:', contextMenuPosition)
}

// 处理右键菜单命令
const handleContextMenuCommand = (command) => {
  if (!currentContextNode.value) return
  
  switch (command) {
    case 'edit':
      handleEditFeature(currentContextNode.value)
      break
    case 'delete':
      handleDeleteFeature(currentContextNode.value.id)
      break
    case 'moveTop':
      handleMoveNode(currentContextNode.value.id, null)
      break
    case 'moveCustom':
      handleOpenMoveDialog(currentContextNode.value.id)
      break
    case 'addCategory':
      handleAddCategoryNode(currentContextNode.value.id)
      break
    case 'addFunction':
      handleAddFunctionNode(currentContextNode.value.id)
      break
    case 'approve':
      handleApproveFeature(currentContextNode.value.id)
      break
    case 'manageVersions':
      handleOpenVersionDialog(currentContextNode.value.id)
      break
    case 'export':
      handleExport(currentContextNode.value)
      break
    default:
      break
  }
  // 关闭右键菜单
  contextMenuVisible.value = false
}

// 打开版本管理对话框
const handleOpenVersionDialog = async (appId) => {
  currentAppId.value = appId
  await loadAppVersions(appId)
  versionDialogVisible.value = true
}

// 加载应用版本列表
const loadAppVersions = async (appId) => {
  try {
    const response = await versionAPI.getAppVersions(appId)
    appVersions.value = response.data
  } catch (error) {
    ElMessage.error('加载版本列表失败')
  }
}

// 添加版本
const handleAddVersion = async () => {
  if (!versionFormRef.value) return
  
  // 确保版本号已生成
  handleVersionInput()
  
  await versionFormRef.value.validate(async (valid) => {
    if (valid) {
      try {
        let username = 'user'
        let userRole = 'developer'
        try {
          username = localStorage.getItem('username') || 'user'
          userRole = localStorage.getItem('role') || 'developer'
        } catch (error) {
          console.error('Error getting localStorage:', error)
        }
        
        await versionAPI.addAppVersion({
          app_id: currentAppId.value,
          version: versionForm.version,
          changelog: versionForm.changelog,
          user_role: userRole
        })
        ElMessage.success('版本添加成功')
        await loadAppVersions(currentAppId.value)
        // 重置表单
        versionForm.version = ''
        versionForm.major = ''
        versionForm.minor = ''
        versionForm.revision = ''
        versionForm.build = ''
        versionForm.changelog = ''
      } catch (error) {
        ElMessage.error(error.response?.data?.message || '版本添加失败')
      }
    }
  })
}

// 删除版本
const handleDeleteVersion = async (versionId) => {
  try {
    await ElMessageBox.confirm('确定要删除这个版本吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    let userRole = 'developer'
    try {
      userRole = localStorage.getItem('role') || 'developer'
    } catch (error) {
      console.error('Error getting localStorage:', error)
    }
    
    await versionAPI.deleteAppVersion(versionId, {
      user_role: userRole
    })
    ElMessage.success('版本删除成功')
    await loadAppVersions(currentAppId.value)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败，请重试')
    }
  }
}

// 打开版本范围选择对话框
const handleOpenVersionRangeDialog = async () => {
  // 获取当前功能所属的应用
  const appRoot = getAppRoot(featureForm.parent_id)
  if (!appRoot) {
    ElMessage.error('无法获取应用信息')
    return
  }
  
  // 加载应用版本列表
  try {
    const response = await versionAPI.getAppVersions(appRoot.id)
    availableVersions.value = response.data
    if (availableVersions.value.length === 0) {
      ElMessage.error('该应用还没有添加版本，请先添加版本')
      return
    }
    
    // 解析当前版本范围
    parseCurrentVersionRange()
    versionRangeDialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载版本列表失败')
  }
}

// 解析当前版本范围
const parseCurrentVersionRange = () => {
  const currentRange = featureForm.version_range
  if (!currentRange) {
    versionRangeForm.rangeType = '>='
    versionRangeForm.startVersion = ''
    versionRangeForm.endVersion = ''
    return
  }
  
  if (currentRange.startsWith('>=')) {
    versionRangeForm.rangeType = '>='
    versionRangeForm.startVersion = currentRange.substring(2).trim()
    versionRangeForm.endVersion = ''
  } else if (currentRange.startsWith('<=')) {
    versionRangeForm.rangeType = '<='
    versionRangeForm.startVersion = currentRange.substring(2).trim()
    versionRangeForm.endVersion = ''
  } else if (currentRange.includes('-')) {
    versionRangeForm.rangeType = '-'
    const parts = currentRange.split('-')
    versionRangeForm.startVersion = parts[0].trim()
    versionRangeForm.endVersion = parts[1].trim()
  }
}

// 确认版本范围选择
const handleConfirmVersionRange = async () => {
  if (!versionRangeFormRef.value) return
  
  await versionRangeFormRef.value.validate((valid) => {
    if (valid) {
      let versionRange = ''
      if (versionRangeForm.rangeType === '>=') {
        versionRange = `>= ${versionRangeForm.startVersion}`
      } else if (versionRangeForm.rangeType === '<=') {
        versionRange = `<= ${versionRangeForm.startVersion}`
      } else if (versionRangeForm.rangeType === '-') {
        versionRange = `${versionRangeForm.startVersion} - ${versionRangeForm.endVersion}`
      }
      featureForm.version_range = versionRange
      versionRangeDialogVisible.value = false
    }
  })
}

// 关闭右键菜单
const closeContextMenu = () => {
  contextMenuVisible.value = false
}

// 处理拖拽放置规则
const handleAllowDrop = (draggingNode, dropNode, dropType) => {
  // 应用节点不支持移动
  if (draggingNode.data.node_type === 'app') {
    return false
  }
  
  // 功能节点不能有子节点
  if (dropType === 'inner' && dropNode.data.node_type === 'function') {
    return false
  }
  
  // 分类节点不能移动到顶层
  if (dropType === 'before' || dropType === 'after') {
    if (draggingNode.data.node_type === 'category' && !dropNode.parent) {
      return false
    }
  }
  
  // 分类节点不能跨应用移动
  if (draggingNode.data.node_type === 'category') {
    const draggingAppRoot = getAppRoot(draggingNode.data.id)
    const dropAppRoot = getAppRoot(dropNode.data.id)
    if (draggingAppRoot && dropAppRoot && draggingAppRoot.id !== dropAppRoot.id) {
      return false
    }
  }
  
  // 检查是否会形成循环引用
  if (dropType === 'inner') {
    let current = dropNode
    while (current) {
      if (current.data.id === draggingNode.data.id) {
        return false
      }
      current = current.parent
    }
  }
  
  return true
}

// 处理拖拽过程中的视觉效果
const handleDragover = (draggingNode, dropNode, dropType) => {
  if (handleAllowDrop(draggingNode, dropNode, dropType)) {
    return 1
  } else {
    return -1
  }
}

// 处理移动确认
const handleMoveConfirmOk = async () => {
  try {
    if (moveConfirmData.dontRemindAgain) {
      setDontRemindAgain(true)
    }
    
    // 添加用户信息和角色信息
    let username = 'user'
    let userRole = 'developer'
    let user_id = '1'
    try {
      username = localStorage.getItem('username') || 'user'
      userRole = localStorage.getItem('role') || 'developer'
      user_id = localStorage.getItem('user_id') || '1'
    } catch (error) {
      console.error('Error getting localStorage:', error)
    }
    
    await featureAPI.moveFeature(moveConfirmData.sourceId, moveConfirmData.targetId, {
      updated_by: username,
      user_role: userRole,
      user_id: user_id
    })
    ElMessage.success('节点移动成功')
    moveConfirmVisible.value = false
    loadData()
  } catch (error) {
    if (error.response && error.response.status === 400) {
      ElMessage.error('移动失败：' + (error.response.data.message || '目标层级已存在同名节点'))
    } else {
      ElMessage.error('移动失败：' + (error.response?.data?.message || '未知错误'))
    }
    moveConfirmVisible.value = false
    loadData()
  }
}

// 处理取消移动
const handleCancelMove = () => {
  moveConfirmVisible.value = false
  loadData()
}

// 处理节点拖拽完成
const handleNodeDrop = async (draggingNode, dropNode, dropType, ev) => {
  try {
    let newParentId = null
    let targetName = ''
    
    if (dropType === 'inner') {
      newParentId = dropNode.data.id
      targetName = dropNode.data.name
    } else if (dropType === 'before' || dropType === 'after') {
      newParentId = dropNode.parent ? dropNode.parent.data.id : null
      targetName = dropNode.parent ? dropNode.parent.data.name : '顶层'
    }
    
    if (getDontRemindAgain()) {
      await featureAPI.moveFeature(draggingNode.data.id, newParentId)
      ElMessage.success('节点移动成功')
      loadData()
    } else {
      moveConfirmData.sourceId = draggingNode.data.id
      moveConfirmData.sourceName = draggingNode.data.name
      moveConfirmData.targetId = newParentId
      moveConfirmData.targetName = targetName
      moveConfirmData.dontRemindAgain = false
      moveConfirmData.moveType = 'drag'
      moveConfirmVisible.value = true
    }
  } catch (error) {
    if (error.response && error.response.status === 400) {
      ElMessage.error('移动失败：' + (error.response.data.message || '目标层级已存在同名节点'))
    } else {
      ElMessage.error('移动失败：' + (error.response?.data?.message || '未知错误'))
    }
    loadData()
  }
}

// 添加应用节点
const handleAddAppNode = () => {
  dialogTitle.value = '添加应用节点'
  Object.keys(featureForm).forEach(key => {
    featureForm[key] = ''
  })
  featureForm.parent_id = null
  featureForm.node_type = 'app'
  featureForm.version_range = 'All'
  featureForm.is_guide_supported = false
  dialogVisible.value = true
}

// 添加分类节点
const handleAddCategoryNode = (parentId) => {
  dialogTitle.value = '添加分类节点'
  Object.keys(featureForm).forEach(key => {
    featureForm[key] = ''
  })
  featureForm.parent_id = parentId
  featureForm.node_type = 'category'
  featureForm.version_range = 'All'
  featureForm.is_guide_supported = false
  dialogVisible.value = true
}

// 添加功能节点
const handleAddFunctionNode = (parentId) => {
  dialogTitle.value = '添加功能节点'
  Object.keys(featureForm).forEach(key => {
    featureForm[key] = ''
  })
  featureForm.parent_id = parentId
  featureForm.node_type = 'function'
  featureForm.is_guide_supported = false
  
  // 初始化动态字段
  initDynamicFields()
  
  dialogVisible.value = true
}

// 添加使用案例
const addUseCase = () => {
  useCasesList.value.push({ value: '' })
}

// 移除使用案例
const removeUseCase = (index) => {
  useCasesList.value.splice(index, 1)
}

// 添加视频
const addVideo = () => {
  videosList.value.push({ value: '' })
}

// 移除视频
const removeVideo = (index) => {
  videosList.value.splice(index, 1)
}

// 初始化动态字段
const initDynamicFields = () => {
  // 初始化使用案例
  useCasesList.value = []
  if (featureForm.use_cases) {
    try {
      // 尝试解析为JSON格式（旧格式，包含类型信息）
      const parsedUseCases = JSON.parse(featureForm.use_cases)
      if (Array.isArray(parsedUseCases)) {
        parsedUseCases.forEach(useCase => {
          useCasesList.value.push({ 
            value: useCase.value || '' 
          })
        })
      } else {
        // 解析失败，回退到简单字符串格式
        const useCases = featureForm.use_cases.split('\n').filter(item => item.trim())
        useCases.forEach(useCase => {
          useCasesList.value.push({ value: useCase })
        })
      }
    } catch (error) {
      // 解析失败，使用简单字符串格式
      const useCases = featureForm.use_cases.split('\n').filter(item => item.trim())
      useCases.forEach(useCase => {
        useCasesList.value.push({ value: useCase })
      })
    }
  } else {
    // 添加一个空的使用案例
    useCasesList.value.push({ value: '' })
  }
  
  // 初始化视频
  videosList.value = []
  if (featureForm.videos) {
    const videos = featureForm.videos.split(',').filter(item => item.trim())
    videos.forEach(video => {
      videosList.value.push({ value: video })
    })
  } else {
    // 添加一个空的视频
    videosList.value.push({ value: '' })
  }
  
  // 初始化设备选择
  if (featureForm.node_type === 'function') {
    if (featureForm.devices === 'all') {
      selectAllDevices.value = true
      selectedDevices.value = []
    } else if (featureForm.devices) {
      selectAllDevices.value = false
      selectedDevices.value = featureForm.devices.split(',').map(id => parseInt(id)).filter(id => !isNaN(id))
    } else {
      selectAllDevices.value = false
      selectedDevices.value = []
    }
  }
}

// 编辑节点
const handleEditFeature = (row) => {
  dialogTitle.value = `编辑${getNodeTypeLabel(row.node_type)}节点`
  Object.keys(featureForm).forEach(key => {
    featureForm[key] = ''
  })
  if (row.node_type === 'app' || row.node_type === 'category') {
    featureForm.id = row.id
    featureForm.name = row.name
    featureForm.description = row.description
    featureForm.parent_id = row.parent_id
    featureForm.node_type = row.node_type
    featureForm.version_range = row.version_range || 'All'
    featureForm.is_guide_supported = false
  } else {
    Object.assign(featureForm, row)
    // 确保is_guide_supported字段存在
    if (featureForm.is_guide_supported === undefined) {
      featureForm.is_guide_supported = false
    }
  }
  
  // 初始化动态字段
  initDynamicFields()
  
  dialogVisible.value = true
}

// 保存节点
const handleSaveFeature = async () => {
  if (!featureFormRef.value) return
  
  // 转换动态字段为字符串格式
  if (featureForm.node_type === 'function') {
    // 转换使用案例为简单的字符串格式
    featureForm.use_cases = useCasesList.value
      .map(item => item.value.trim())
      .filter(item => item)
      .join('\n')
    
    // 转换视频为逗号分隔的字符串
    featureForm.videos = videosList.value
      .map(item => item.value.trim())
      .filter(item => item)
      .join(',')
    
    // 处理设备字段
    if (selectAllDevices.value) {
      featureForm.devices = 'all'
    } else {
      featureForm.devices = selectedDevices.value.join(',')
    }
  }
  
  // 添加用户信息和角色信息
  let username = 'user'
  let userRole = 'developer'
  let user_id = '1'
  try {
    username = localStorage.getItem('username') || 'user'
    userRole = localStorage.getItem('role') || 'developer'
    user_id = localStorage.getItem('user_id') || '1'
  } catch (error) {
    console.error('Error getting localStorage:', error)
  }
  
  await featureFormRef.value.validate(async (valid) => {
    if (valid) {
      try {
        if (featureForm.id) {
          await featureAPI.updateFeature(featureForm.id, {
            ...featureForm,
            updated_by: username,
            user_role: userRole,
            user_id: user_id
          })
          ElMessage.success(`${getNodeTypeLabel(featureForm.node_type)}节点更新成功`)
        } else {
          await featureAPI.createFeature({
            ...featureForm,
            created_by: username,
            user_role: userRole,
            user_id: user_id
          })
          ElMessage.success(`${getNodeTypeLabel(featureForm.node_type)}节点添加成功`)
        }
        dialogVisible.value = false
        loadData()
        selectedFeature.value = null
      } catch (error) {
        if (error.response && error.response.status === 400) {
          ElMessage.error(error.response.data.message || '操作失败：同层级已存在同名节点')
        } else {
          ElMessage.error('操作失败，请重试')
        }
      }
    }
  })
}

// 审核通过节点
const handleApproveFeature = async (id) => {
  try {
    let username = 'admin'
    try {
      username = localStorage.getItem('username') || 'admin'
    } catch (error) {
      console.error('Error getting localStorage:', error)
    }
    // 调用审核API
    await featureAPI.approveFeature(id, {
      approved_by: username
    })
    ElMessage.success('节点审核通过成功')
    loadData()
    selectedFeature.value = null
  } catch (error) {
    if (error.response && error.response.status === 400 && error.response.data.message === '该审核已失效') {
      ElMessage.warning('该审核已失效')
    } else {
      ElMessage.error('审核失败，请重试')
    }
  }
}

// 撤回审核
const handleWithdrawAudit = async (id) => {
  try {
    let username = 'user'
    try {
      username = localStorage.getItem('username') || 'user'
    } catch (error) {
      console.error('Error getting localStorage:', error)
    }
    // 调用撤回审核API
    await featureAPI.withdrawAudit(id, {
      withdrawn_by: username
    })
    ElMessage.success('审核撤回成功')
    loadData()
    selectedFeature.value = null
  } catch (error) {
    ElMessage.error('撤回审核失败，请重试')
  }
}

// 删除节点
const handleDeleteFeature = async (id) => {
  try {
    await ElMessageBox.confirm('确定要删除这个节点吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    // 添加用户信息和角色信息
    let username = 'user'
    let userRole = 'developer'
    let user_id = '1'
    try {
      username = localStorage.getItem('username') || 'user'
      userRole = localStorage.getItem('role') || 'developer'
      user_id = localStorage.getItem('user_id') || '1'
    } catch (error) {
      console.error('Error getting localStorage:', error)
    }
    
    await featureAPI.deleteFeature(id, {
      deleted_by: username,
      user_role: userRole,
      user_id: user_id
    })
    ElMessage.success('节点删除成功')
    loadData()
    selectedFeature.value = null
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败，请重试')
    }
  }
}

// 获取节点类型标签
const getNodeTypeLabel = (nodeType) => {
  switch (nodeType) {
    case 'app':
      return '应用'
    case 'category':
      return '分类'
    case 'function':
      return '功能'
    default:
      return '未知'
  }
}

// 检查字符串是否为有效的 JSON
const isValidJSON = (str) => {
  try {
    JSON.parse(str)
    return true
  } catch (error) {
    return false
  }
}

// 解析使用案例数据
const parseUseCases = (useCasesStr) => {
  try {
    const parsed = JSON.parse(useCasesStr)
    return Array.isArray(parsed) ? parsed : []
  } catch (error) {
    return []
  }
}

// 获取使用案例类型标签
const getUseCaseTypeLabel = (type) => {
  const typeMap = {
    'basic': '基础操作',
    'advanced': '高级功能',
    'best_practice': '最佳实践',
    'faq': '常见问题'
  }
  return typeMap[type] || type || '未分类'
}

// 根据设备ID获取设备发布名称和年份
const getDeviceName = (deviceId) => {
  const device = availableDevices.value.find(d => d.id === deviceId)
  return device ? `${device.release_name} ${device.release_year}` : `设备${deviceId}`
}

// 格式化设备列表
const formatDeviceList = (devicesStr) => {
  if (!devicesStr) return '无'
  return devicesStr.split(',').map(id => getDeviceName(parseInt(id))).join(', ')
}

// 分割线拖拽相关函数
const startDrag = (e) => {
  isDragging.value = true
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}

const onDrag = (e) => {
  if (!isDragging.value) return
  
  const container = document.querySelector('.features-content')
  if (!container) return
  
  const containerRect = container.getBoundingClientRect()
  const containerWidth = containerRect.width
  const mouseX = e.clientX - containerRect.left
  
  let newWidth = (mouseX / containerWidth) * 100
  newWidth = Math.max(20, Math.min(80, newWidth))
  
  treeWidth.value = newWidth
}

const stopDrag = () => {
  isDragging.value = false
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

// 处理导出
const handleExport = (node) => {
  console.log('Export function called with node:', node)
  console.log('Node type:', node?.node_type)
  if (node && node.node_type !== 'app') {
    console.log('Node is not an app, returning')
    return
  }
  console.log('Setting exportDialogVisible.value to true')
  exportDialogVisible.value = true
  console.log('exportDialogVisible.value:', exportDialogVisible.value)
  // 强制更新UI
  setTimeout(() => {
    console.log('After timeout, exportDialogVisible.value:', exportDialogVisible.value)
  }, 100)
}

// 确认导出
const confirmExport = async () => {
  if (!currentContextNode.value || currentContextNode.value.node_type !== 'app') return
  
  isExporting.value = true
  try {
    // 获取应用ID
    const appId = currentContextNode.value.id
    const appName = currentContextNode.value.name || 'app'
    
    // 调用后端API导出zip文件，传递模板内容
    const response = await api.post(`/features/${appId}/export`, {
      template: exportTemplate.value
    }, {
      responseType: 'blob'
    })
    
    // 处理blob响应
    const blob = response.data
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${appName}_导出.zip`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    
    ElMessage.success('成功导出功能文件到压缩包')
  } catch (error) {
    console.error('导出失败:', error)
    ElMessage.error(error.message || '导出失败，请稍后重试')
  } finally {
    isExporting.value = false
    exportDialogVisible.value = false
  }
}

// 获取应用下的所有功能
const getAllFeaturesUnderApp = async (appId) => {
  const allFeatures = []
  
  const traverseFeatures = (features) => {
    for (const feature of features) {
      allFeatures.push(feature)
      if (feature.children && feature.children.length > 0) {
        traverseFeatures(feature.children)
      }
    }
  }
  
  // 从featuresTree中查找应用节点
  const appNode = findAppNode(featuresTree.value, appId)
  if (appNode && appNode.children) {
    traverseFeatures(appNode.children)
  }
  
  return allFeatures
}

// 查找应用节点
const findAppNode = (nodes, appId) => {
  for (const node of nodes) {
    if (node.id === appId) {
      return node
    }
    if (node.children) {
      const found = findAppNode(node.children, appId)
      if (found) {
        return found
      }
    }
  }
  return null
}

// 根据模板生成markdown内容
const generateMarkdown = (feature, template, featuresTree) => {
  let content = template
  
  // 计算祖先路径
  const ancestorPath = calculateAncestorPath(feature.id, featuresTree)
  
  // 替换单值字段
  content = content.replace(/\{\{name\}\}/g, feature.name || '无')
  content = content.replace(/\{\{description\}\}/g, feature.description || '无')
  content = content.replace(/\{\{version_range\}\}/g, feature.version_range || '无')
  content = content.replace(/\{\{node_type\}\}/g, getNodeTypeLabel(feature.node_type) || '无')
  content = content.replace(/\{\{status\}\}/g, feature.status || '无')
  content = content.replace(/\{\{ancestor_path\}\}/g, ancestorPath || '无')
  content = content.replace(/\{\{created_at\}\}/g, feature.created_at || '无')
  content = content.replace(/\{\{updated_at\}\}/g, feature.updated_at || '无')
  
  // 处理use_cases多值字段
  content = processMultiValueField(content, 'use_cases', feature.use_cases)
  
  // 处理videos多值字段
  content = processMultiValueField(content, 'videos', feature.videos)
  
  return content
}

// 计算祖先路径
const calculateAncestorPath = (featureId, featuresTree) => {
  const path = []
  
  const findNodePath = (nodes, targetId) => {
    for (const node of nodes) {
      if (node.id === targetId) {
        path.unshift(node.name)
        return true
      }
      if (node.children && node.children.length > 0) {
        if (findNodePath(node.children, targetId)) {
          path.unshift(node.name)
          return true
        }
      }
    }
    return false
  }
  
  findNodePath(featuresTree, featureId)
  return path.join('-')
}

// 处理多值字段
const processMultiValueField = (content, fieldName, fieldValue) => {
  const regex = new RegExp(`\\{\\{#${fieldName}\\}\\}(.*?)\\{\\{/${fieldName}\\}\\}`,'s')
  
  if (!fieldValue) {
    return content.replace(regex, '无')
  }
  
  let items = []
  
  if (fieldName === 'use_cases') {
    if (typeof fieldValue === 'string') {
      if (isValidJSON(fieldValue)) {
        items = JSON.parse(fieldValue)
      } else {
        items = [{ value: fieldValue }]
      }
    } else if (Array.isArray(fieldValue)) {
      items = fieldValue
    }
  } else if (fieldName === 'videos') {
    if (typeof fieldValue === 'string') {
      items = fieldValue.split(',').filter(v => v.trim()).map(url => ({ url: url.trim() }))
    }
  }
  
  if (items.length === 0) {
    return content.replace(regex, '无')
  }
  
  const match = content.match(regex)
  if (!match) {
    return content
  }
  
  const template = match[1]
  let renderedContent = ''
  
  for (let i = 0; i < items.length; i++) {
    let itemContent = template
    itemContent = itemContent.replace(/\{\{index\}\}/g, i)
    itemContent = itemContent.replace(/\{\{value\}\}/g, items[i].value || items[i].url || '无')
    itemContent = itemContent.replace(/\{\{url\}\}/g, items[i].url || items[i].value || '无')
    renderedContent += itemContent
  }
  
  return content.replace(regex, renderedContent)
}

// 下载文件
const downloadFile = (content, filename, mimeType) => {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

onMounted(() => {
  loadData()
  loadDevices()
  // 添加点击外部关闭右键菜单的事件监听器
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('contextmenu', handleClickOutside)
})

onUnmounted(() => {
  // 移除事件监听器
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('contextmenu', handleClickOutside)
})

// 处理点击外部关闭右键菜单
const handleClickOutside = (event) => {
  const contextMenu = document.querySelector('.custom-context-menu')
  if (contextMenu && !contextMenu.contains(event.target)) {
    contextMenuVisible.value = false
  }
}

// 处理对话框关闭
const handleClose = (done) => {
  done()
}
</script>

<style scoped>
.features-container {
  padding: 0;
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
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

.mb-4 {
  margin-bottom: 0;
  border-radius: 0;
  border-left: none;
  border-right: none;
  border-top: none;
}

/* 功能内容布局 */
.features-content {
  display: flex;
  flex: 1;
  position: relative;
  min-height: 0;
}

/* 左侧树形结构 */
.tree-panel {
  height: 100%;
  transition: width 0.3s ease;
  overflow: hidden;
}

/* 树形结构容器 */
.tree-container {
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  border-radius: 0;
  border: none;
}

/* 功能树样式 */
.tree-container :deep(.el-tree) {
  flex: 1;
  overflow-y: auto;
}

.tree-container h3 {
  margin: 0 0 15px 0;
  font-size: 16px;
  color: #303133;
}

/* 分割线 */
.splitter {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1px;
  background-color: #e4e7ed;
  cursor: col-resize;
  transition: background-color 0.3s ease;
  z-index: 10;
}

.splitter:hover {
  background-color: #409eff;
}

.splitter:active {
  background-color: #409eff;
}

/* 右侧详细信息 */
.detail-panel {
  height: 100%;
  transition: width 0.3s ease;
  overflow: hidden;
  margin-left: 1px;
}

/* 详细信息容器 */
.detail-container {
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  border-radius: 0;
  border: none;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.detail-header h3 {
  margin: 0;
  font-size: 16px;
  color: #303133;
}

.detail-content {
  flex: 1;
  overflow-y: auto;
}

/* 确保整个页面适配浏览器视窗 */
.features-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.features-content {
  flex: 1;
  display: flex;
  min-height: 0;
}

/* 优化滚动条样式 */
.tree-container :deep(.el-tree)::-webkit-scrollbar,
.detail-content::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.tree-container :deep(.el-tree)::-webkit-scrollbar-track,
.detail-content::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.tree-container :deep(.el-tree)::-webkit-scrollbar-thumb,
.detail-content::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.tree-container :deep(.el-tree)::-webkit-scrollbar-thumb:hover,
.detail-content::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

.empty-detail {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 300px;
}



/* 使用案例样式 */
.use-case-item-detail {
  margin-bottom: 15px;
}

.use-case-type {
  margin-bottom: 8px;
}

.use-case-content {
  line-height: 1.5;
}

/* 树形节点样式 */
.tree-node {
  display: flex;
  align-items: center;
}

.tree-node .node-emoji {
  margin-right: 8px;
  font-size: 14px;
}

.tree-node .node-status {
  margin-left: 8px;
}

.status-pending {
  color: #E6A23C;
}

/* 描述预览样式 */
.description-preview {
  cursor: pointer;
  line-height: 1.5;
}

.description-preview:hover {
  text-decoration: underline;
}

/* 视频链接样式 */
.video-link {
  display: inline-block;
  margin-right: 10px;
  color: #409EFF;
  text-decoration: none;
}

.video-link:hover {
  text-decoration: underline;
}

/* 对比面板样式 */
.audit-comparison {
  margin-bottom: 20px;
}

.comparison-panel {
  margin-top: 10px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 右键菜单样式 */
.custom-context-menu {
  z-index: 999999;
}

.context-menu-item {
  padding: 8px 16px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.context-menu-item:hover {
  background-color: #f5f7fa;
}

.context-menu-divider {
  height: 1px;
  background-color: #ebeef5;
  margin: 4px 0;
}

.context-menu-item-header {
  padding: 8px 16px;
  font-weight: bold;
  color: #909399;
}

/* 编辑对话框样式 */
.el-dialog .el-tabs {
  width: 100%;
}

.el-dialog .el-tabs__content {
  padding: 10px 0;
}

.el-dialog .markdown-preview {
  min-height: 200px;
  line-height: 1.5;
}

.el-dialog .markdown-full-preview {
  min-height: 300px;
  line-height: 1.5;
}

/* 导出对话框样式 */
.export-dialog {
  --el-dialog-height: 90vh;
}

.export-dialog .el-dialog__body {
  min-height: 600px;
  max-height: 75vh;
  overflow-y: auto;
  padding: 20px;
}

.export-dialog .el-textarea {
  min-height: 400px;
  height: 400px;
}

.export-dialog .el-textarea__inner {
  min-height: 400px;
  height: 100%;
}
</style>