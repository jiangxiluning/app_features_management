# 接口设计文档

基础路径：`/api`  
数据格式：JSON（`Content-Type: application/json`）  
开发代理：前端 Vite `http://localhost:3000` → 后端 `http://localhost:5002`

---

## 1. 通用约定

### 1.1 鉴权

| 级别 | 说明 | 用法 |
|------|------|------|
| 公开 | 无需 Token | 仅 `POST /api/auth/login` |
| 登录用户 | 有效 JWT | `Authorization: Bearer <access_token>` |
| 管理员 | JWT 且 `role=admin` | 用户管理、备份、审核批准等 |

JWT Claims：

```json
{
  "sub": "username",
  "role": "admin|developer",
  "user_id": 1
}
```

Token 有效期：**8 小时**。

密码：前端使用 SHA-256 哈希后传输，后端存储哈希值。

### 1.2 通用响应

**成功：**

```json
{ "message": "操作说明", "revision": 2 }
```

**错误：**

```json
{ "message": "错误描述", "revision": 3 }
```

| HTTP 状态码 | 含义 |
|-------------|------|
| 400 | 参数校验失败 |
| 401 | 未登录或 Token 无效 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 409 | revision 冲突 / 审核已失效 |
| 503 | 维护模式（备份恢复中） |

### 1.3 维护模式

`restore_backup`、`import_database` 执行期间，`maintenance_mode=true`，所有写操作（POST/PUT/DELETE/PATCH）返回 **503**。

---

## 2. 认证接口

### POST `/api/auth/login`

公开。登录获取 Token。

**请求：**

```json
{
  "username": "admin",
  "password": "<sha256_hex>"
}
```

**响应 200：**

```json
{
  "access_token": "<jwt>",
  "role": "admin",
  "username": "admin",
  "user_id": 1
}
```

### POST `/api/auth/register`

管理员。创建用户。

**请求：**

```json
{
  "username": "dev1",
  "password": "<sha256_hex>",
  "role": "developer"
}
```

### POST `/api/auth/change-password`

登录用户。修改自己的密码。

**请求：**

```json
{
  "old_password": "<sha256_hex>",
  "new_password": "<sha256_hex>"
}
```

---

## 3. SSE 实时推送

### GET `/api/events?token=<jwt>`

登录用户。Server-Sent Events 长连接。

> EventSource 无法设置 Header，Token 通过 query 传递。

**事件类型：**

| event | 说明 |
|-------|------|
| `connected` | 连接成功 |
| `data_change` | 数据变更广播 |

**data_change 载荷：**

```json
{
  "seq": 12,
  "at": "2026-06-19T05:19:00Z",
  "type": "features_changed",
  "scope": "features",
  "actor": "admin",
  "resource_id": 6
}
```

| type | 触发场景 |
|------|----------|
| `features_changed` | 功能增删改移、审核结果生效 |
| `audit_submitted` | 开发者提交待审 |
| `audit_approved` | 审核通过 |
| `audit_rejected` | 审核拒绝 |
| `audit_withdrawn` | 撤回审核 |

每 25 秒发送 keepalive 注释行。

---

## 4. 用户与应用授权

### GET `/api/users`

管理员。用户列表。

### PUT `/api/users/:id`

管理员。更新密码/角色。

### DELETE `/api/users/:id`

管理员。删除用户。

### GET `/api/user-apps`

管理员。全部授权关系。

### GET `/api/user-apps/:user_id`

登录用户（本人或管理员）。某用户可访问的应用。

### POST `/api/user-apps`

管理员。分配应用权限。

```json
{ "user_id": 2, "app_id": 1 }
```

### DELETE `/api/user-apps/:id`

管理员。移除授权。

---

## 5. 功能树（核心）

### GET `/api/features`

登录用户。获取功能树。

**Query：**

| 参数 | 说明 |
|------|------|
| `include_pending` | 仅管理员有效，默认 `false` |
| `page` | 页码（树接口保留参数，当前返回全量） |
| `page_size` | 每页大小 |

**响应：**

```json
{
  "data": [
    {
      "id": 1,
      "name": "应用名",
      "node_type": "app",
      "status": "approved",
      "revision": 1,
      "children": []
    }
  ],
  "total": 10,
  "page": 1,
  "page_size": 20
}
```

COW 读模型：开发者仅见授权应用；他人不见未审新建；pending 草稿仅提交人/管理员可见。

### POST `/api/features`

登录用户。创建节点。

**请求（function 示例）：**

```json
{
  "name": "功能名",
  "description": "描述",
  "parent_id": 2,
  "node_type": "function",
  "version_range": "1.0",
  "is_guide_supported": false
}
```

- 开发者：创建 pending + audit_log
- 管理员：直接 approved

### PUT `/api/features/:id`

登录用户。更新节点。

**管理员额外字段：**

```json
{
  "description": "新描述",
  "revision": 3
}
```

revision 不匹配 → **409**。

开发者：仅写 audit_log，不改已发布正文。

### DELETE `/api/features/:id`

登录用户。删除节点。

- 开发者：提交 delete 审核（COW）
- 管理员：直接递归删除（含 audit_log 清理）

### POST `/api/features/:id/move`

登录用户。移动节点。

```json
{
  "new_parent_id": 5,
  "revision": 2
}
```

`new_parent_id` 为 `null` 表示移至顶层（category 不可）。

### POST `/api/features/:app_id/export`

登录用户（`admin` / `developer`）。导出应用下**已审核**功能节点为 Markdown ZIP。

**Body：**

```json
{
  "template": "# {{name}}\n\n{{description}}",
  "feature_ids": [1, 3, 5]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `template` | string | 否 | Markdown 模板；省略时使用默认模板 |
| `feature_ids` | int[] | 否 | 要导出的功能 ID；省略时导出该应用下全部已审核功能 |

**模板占位符（常用）：**

| 占位符 | 含义 |
|--------|------|
| `{{name}}` | 功能名称 |
| `{{description}}` | 功能描述 |
| `{{version_range}}` | 版本范围 |
| `{{is_guide_supported}}` | 是否支持引导 |
| `{{#use_cases}}...{{/use_cases}}` | 典型使用案例列表 |
| `{{#videos}}...{{/videos}}` | 教学视频列表 |
| `{{#devices}}...{{/devices}}` | 不支持设备列表 |

**响应 200：** `application/zip` 附件，文件名 `{应用名}_导出.zip`。

**错误：**

| 状态码 | 场景 |
|--------|------|
| 400 | 无已审核功能可导出；`feature_ids` 格式无效；过滤后无匹配功能 |
| 404 | 应用不存在 |

**前端调用场景（0.9.1）：**

| 入口 | 传参 |
|------|------|
| 应用右键「导出知识描述」 | 省略 `feature_ids`（全量） |
| 树多选 / 功能右键 | 传 `feature_ids` 为选中 ID 列表 |

### 功能属性 JSON 导出（纯前端）

「导出功能属性文件」**不调用后端 API**。前端 [`Features.vue`](../../frontend/src/views/Features.vue) 从功能树组装 JSON 数组并触发浏览器下载。

导出字段示例：

```json
[
  {
    "id": 6,
    "name": "功能名",
    "version_range": ">= 1.0.0.0",
    "is_guide_supported": true,
    "unsupported_devices": ["iPhone15,1"],
    "created_at": "2026-06-19 10:00:00"
  }
]
```

| 入口 | 范围 |
|------|------|
| 应用右键 | 应用下全部 function 节点 |
| 树多选 / 功能右键 | 仅选中 ID 对应节点 |

---

## 6. 审核接口

### GET `/api/audit-logs`

登录用户。查询审核记录。

**Query：**

| 参数 | 说明 |
|------|------|
| `feature_id` | 按功能过滤 |
| `created_by` | 按创建者过滤 |
| `date` | 单日 `YYYY-MM-DD` |
| `start_date` / `end_date` | 日期范围 |

### POST `/api/audit-logs/:id/approve`

管理员。批准（原子 `pending→approved`）。

```json
{ "approved_by": "admin" }
```

重复批准 → **409**。

### POST `/api/audit-logs/:id/reject`

管理员。拒绝并回滚。

### POST `/api/audit-logs/:id/withdraw`

登录用户（仅创建者）。撤回。

---

## 7. 应用版本

### GET `/api/app-versions/:app_id`

登录用户。版本列表。

### POST `/api/app-versions`

管理员。新增版本。

```json
{
  "app_id": 1,
  "version": "1.0.0.0",
  "changelog": "更新说明"
}
```

### DELETE `/api/app-versions/:id`

管理员。删除版本。

---

## 8. 设备管理

### GET `/api/devices`

登录用户。设备列表。

### POST `/api/devices`

管理员。创建设备。

### PUT `/api/devices/:id`

管理员。更新设备。

### DELETE `/api/devices/:id`

管理员。删除设备。

---

## 9. 统计

### GET `/api/statistics`

登录用户。全局及应用维度统计（功能数、分类数、视频数、pending 数）。

---

## 10. 备份与恢复

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/backup/config` | 管理员 | 读取备份配置 |
| PUT | `/api/backup/config` | 管理员 | 固定返回 403（仅改 config.yaml） |
| POST | `/api/backup/trigger` | 管理员 | 手动触发备份 |
| GET | `/api/backup/list` | 管理员 | 备份文件列表 |
| DELETE | `/api/backup/delete/:filename` | 管理员 | 删除备份 |
| POST | `/api/backup/restore/:filename` | 管理员 | 恢复备份（维护模式） |
| POST | `/api/backup/import` | 管理员 | 上传 `.db` 导入（维护模式） |

导入接口：`multipart/form-data`，字段名 `file`。

---

## 11. 大模型

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/llm/config` | 管理员 | 获取配置 |
| POST | `/api/llm/config` | 管理员 | 保存配置 |
| POST | `/api/llm/test` | 管理员 | 测试连接 |
| POST | `/api/llm/optimize` | 登录用户 | 优化功能描述 |

**optimize 请求：**

```json
{ "feature_id": 6 }
```

---

## 12. 接口与页面对照

| 前端页面 | 主要接口 |
|----------|----------|
| Login | `/api/auth/login` |
| Features | `/api/features`, `/api/features/:app_id/export`, `/api/devices`, `/api/llm/optimize`, `/api/events` |
| AuditApproval | `/api/audit-logs`, approve/reject |
| AuditLog | `/api/audit-logs` |
| Users | `/api/users`, `/api/auth/register`, `/api/user-apps` |
| Devices | `/api/devices` |
| Backup | `/api/backup/*` |
| Statistics | `/api/statistics` |
| LLMManagement | `/api/llm/*` |

---

## 13. 测试脚本

| 脚本 | 用途 |
|------|------|
| `backend/run_plan_tests.py` | 迁移 + 一致性集成测试 |
| `backend/test_sse_e2e.py` | SSE 端到端测试 |
| `backend/test_migration_2_0_0.py` | 2.0.0 迁移测试 |

```bash
cd backend
python3 run_plan_tests.py
python3 test_sse_e2e.py
```
