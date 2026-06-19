# 项目架构

## 1. 概述

本系统为**前后端分离**的 App 功能知识管理平台，用于管理树形功能节点（应用 → 分类 → 功能）、开发者审核流、设备信息、数据备份及 LLM 辅助描述优化。

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + Vite + Element Plus + Vue Router |
| 后端 | Flask + Flask-SQLAlchemy + Flask-JWT-Extended |
| 数据库 | SQLite（单文件，`instance/app_knowledge.db`） |
| 实时通知 | SSE（Server-Sent Events，`/api/events`） |

---

## 2. 逻辑结构

```mermaid
flowchart TB
    subgraph clients [客户端]
        Browser[浏览器 SPA]
    end

    subgraph frontend [前端 Vue3]
        Router[Vue Router]
        Views[Views 页面]
        API[api/index.js]
        SSE[useDataChangeSSE]
        Bus[dataChangeBus]
        Router --> Views
        Views --> API
        Views --> Bus
        Home[Home.vue] --> SSE
        SSE --> Bus
    end

    subgraph backend [后端 Flask]
        App[app.py 路由层]
        Consistency[consistency.py]
        SSEHub[sse_hub.py]
        Services[services/llm_service.py]
        App --> Consistency
        App --> SSEHub
        App --> Services
    end

    subgraph storage [存储]
        SQLite[(SQLite WAL)]
        Backups[backups/*.db]
    end

    Browser --> frontend
    API -->|REST /api/*| App
    SSE -->|SSE /api/events| App
    App --> SQLite
    App --> Backups
```

### 2.1 后端模块职责

| 模块 | 路径 | 职责 |
|------|------|------|
| 应用入口 | `backend/app.py` | 模型定义、REST 路由、备份调度、DB 初始化 |
| 一致性层 | `backend/consistency.py` | JWT 鉴权、COW 读模型、revision 锁、审计 JSON、SSE 发射 |
| SSE 中心 | `backend/sse_hub.py` | 内存发布/订阅（要求 Gunicorn `-w 1`） |
| 迁移 | `backend/migrations/migrate_to_2_0_0.py` | Schema 2.0.0 全量迁移 |
| LLM | `backend/services/llm_service.py` | 大模型调用封装 |

### 2.2 前端模块职责

| 模块 | 路径 | 职责 |
|------|------|------|
| 路由 | `frontend/src/router/index.js` | 页面路由、登录守卫 |
| API | `frontend/src/api/index.js` | Axios 封装、Token 注入、401 跳转 |
| SSE | `frontend/src/composables/useDataChangeSSE.js` | EventSource 连接、变更通知 |
| 事件总线 | `frontend/src/utils/dataChangeBus.js` | 页面内「立即刷新」联动 |
| 功能树 | `frontend/src/views/Features.vue` | 核心业务 UI |

---

## 3. 核心时序

### 3.1 认证流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant FE as 前端
    participant API as POST /api/auth/login
    participant DB as SQLite

    U->>FE: 输入用户名/密码
    FE->>FE: SHA-256 哈希密码
    FE->>API: {username, password_hash}
    API->>DB: 查询 User
    API->>API: 比对密码哈希
    API-->>FE: access_token, role, user_id
    FE->>FE: localStorage 存储 token
    FE->>API: 后续请求 Authorization Bearer
```

### 3.2 COW 审核写入（开发者）

```mermaid
sequenceDiagram
    participant Dev as 开发者
    participant API as PUT /api/features/:id
    participant F as feature 表
    participant A as audit_log 表
    participant SSE as sse_hub

    Dev->>API: 提交修改（JWT）
    API->>F: 读取当前快照 before_content
    Note over F: 不修改正文，仅 status=pending
    API->>A: 写入 pending audit（after_content=草稿）
    API->>SSE: emit_data_change
    API-->>Dev: 200 已提交审核
```

### 3.3 COW 读取隔离

```mermaid
sequenceDiagram
    participant Owner as 提交人
    participant Other as 其他用户
    participant API as GET /api/features
    participant RV as resolve_feature_view

    Owner->>API: 请求功能树
    API->>RV: viewer=owner
    RV-->>Owner: 合并 after_content 草稿

    Other->>API: 请求功能树
    API->>RV: viewer=other
    RV-->>Other: 仅已发布快照（status 显示 approved）
```

### 3.4 管理员审核批准

```mermaid
sequenceDiagram
    participant Admin as 管理员
    participant API as POST /api/audit-logs/:id/approve
    participant A as audit_log
    participant F as feature
    participant SSE as sse_hub

    Admin->>API: 批准
    API->>A: UPDATE status=pending → approved（原子）
    alt action=update/move
        API->>F: apply after_content + bump revision
    else action=delete
        API->>F: 递归删除
    end
    API->>SSE: features_changed + audit_approved
    API-->>Admin: 200
```

### 3.5 SSE 数据变更通知

```mermaid
sequenceDiagram
    participant A as 用户 A（浏览中）
    participant B as 用户 B（修改数据）
    participant SSE as GET /api/events
    participant Hub as sse_hub
    participant API as 写 API

    A->>SSE: EventSource ?token=JWT
    SSE-->>A: event: connected
    B->>API: PUT /api/features/:id
    API->>Hub: broadcast_data_change
    Hub-->>A: event: data_change
    A->>A: 弹窗「数据已更新」+ 立即刷新
```

### 3.6 revision 乐观锁（管理员）

```mermaid
sequenceDiagram
    participant A as 管理员 A
    participant B as 管理员 B
    participant API as PUT /api/features/:id

    A->>API: revision=3
    API-->>A: 200, revision=4
    B->>API: revision=3（过期）
    API-->>B: 409 数据已被他人修改
```

---

## 4. 类图（核心领域模型）

```mermaid
classDiagram
    class User {
        +int id
        +string username
        +string password
        +string role
    }

    class UserApp {
        +int id
        +int user_id
        +int app_id
    }

    class Feature {
        +int id
        +string name
        +string description
        +string node_type
        +string status
        +int parent_id
        +int revision
        +datetime updated_at
    }

    class AuditLog {
        +int id
        +int feature_id
        +string action
        +string status
        +text before_content
        +text after_content
    }

    class Device {
        +int id
        +string device_model
        +int release_year
    }

    class AppVersion {
        +int id
        +int app_id
        +string version
    }

    class LLMConfig {
        +int id
        +string base_url
        +string model_name
    }

    class SchemaVersion {
        +int id
        +string version
    }

    User "1" --> "*" UserApp
    Feature "1" --> "*" UserApp : app 节点
    Feature "1" --> "*" Feature : parent/children
    Feature "1" --> "*" AuditLog
    Feature "1" --> "*" AppVersion
```

### 4.1 一致性辅助模块（非 ORM）

```mermaid
classDiagram
    class consistency {
        +parse_audit_content(raw)
        +feature_snapshot(feature)
        +resolve_feature_view(...)
        +check_revision_conflict(feature, data)
        +emit_data_change(...)
        +auth_required
        +admin_required
    }

    class sse_hub {
        +subscribe()
        +unsubscribe(q)
        +broadcast_data_change(payload)
        +format_sse(name, data)
    }

    consistency --> sse_hub : emit_data_change
```

---

## 5. 数据库设计

### 5.1 ER 关系

```mermaid
erDiagram
    user ||--o{ user_app : assigns
    feature ||--o{ user_app : "app node"
    feature ||--o{ feature : "parent_id"
    feature ||--o{ audit_log : has
    feature ||--o{ app_version : has

    user {
        int id PK
        string username UK
        string password
        string role
    }

    feature {
        int id PK
        string name
        text description
        int parent_id FK
        string node_type
        string status
        int revision
        datetime updated_at
    }

    audit_log {
        int id PK
        int feature_id FK
        string action
        string status
        text before_content
        text after_content
    }

    user_app {
        int id PK
        int user_id FK
        int app_id FK
    }

    device {
        int id PK
        string device_model UK
    }

    app_version {
        int id PK
        int app_id FK
        string version
    }

    schema_version {
        int id PK
        string version UK
    }

    llm_config {
        int id PK
        string name
    }
```

### 5.2 表说明

| 表名 | 说明 |
|------|------|
| `user` | 系统用户（admin / developer） |
| `user_app` | 开发者可访问的应用授权 |
| `feature` | 树形功能节点（app / category / function） |
| `audit_log` | 审核记录，COW 草稿与快照 |
| `device` | 终端设备型号 |
| `app_version` | 应用版本与 changelog |
| `schema_version` | 数据库 schema 版本链 |
| `llm_config` | 大模型连接配置 |

### 5.3 Schema 版本演进

| 版本 | 来源 | 主要变更 |
|------|------|----------|
| 1.0.1 | 应用首次启动默认 | 基础表结构 |
| 1.1.0 | `migrate_database.py` | 新增 `llm_config` |
| 2.0.0 | `migrations/migrate_to_2_0_0.py` | `revision`/`updated_at`、audit JSON、pending 回迁、唯一索引 |

### 5.4 索引与约束

```sql
-- 2.0.0 迁移后
CREATE UNIQUE INDEX idx_feature_parent_name
ON feature(parent_id, name)
WHERE parent_id IS NOT NULL;
```

SQLite 连接级配置（每次连接执行）：

- `PRAGMA journal_mode=WAL`
- `PRAGMA busy_timeout=5000`
- `PRAGMA foreign_keys=ON`

### 5.5 节点类型与状态

**node_type：** `app` → `category` → `function`（树形父子）

**status：**

| 值 | 含义 |
|----|------|
| `approved` | 已发布 |
| `pending` | 有待审变更（COW 下行内可能仍为已发布内容） |
| `rejected` | 审核拒绝（历史状态） |

**audit_log.action：** `create` | `update` | `delete` | `move`

---

## 6. 部署架构

```mermaid
flowchart LR
    subgraph prod [生产推荐]
        Nginx[Nginx 静态资源]
        Gunicorn[Gunicorn w=1]
        SQLite[(app_knowledge.db)]
    end

    Browser --> Nginx
    Nginx -->|/api| Gunicorn
    Gunicorn --> SQLite
```

**约束：**

- Gunicorn 必须 **单 worker**（`-w 1`），否则 SSE 内存广播无法跨进程
- 禁止多机共享同一 SQLite 文件
- 备份/恢复期间进入 `maintenance_mode`，阻断写 API

---

## 7. 安全模型

| 角色 | 能力 |
|------|------|
| `admin` | 全功能；直接写库；审核；用户/备份/设备管理 |
| `developer` | 授权应用内 COW 提交；查看已发布 + 自己的草稿 |

鉴权方式：JWT Bearer（8 小时过期），角色从 Token claims 读取，**不信任**请求体中的 `user_role`。
