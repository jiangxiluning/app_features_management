# 前端部署文档

## 项目介绍

这是一个基于Vue 3的前端项目，使用Vite作为构建工具。本文档详细说明了如何部署该前端项目。

## 环境要求

- Node.js 14.0 或更高版本
- npm 6.0 或更高版本

## 部署步骤

### 1. 准备工作

1. 克隆项目代码到本地或服务器
2. 进入前端项目目录：
   ```bash
   cd frontend
   ```

### 2. 配置部署参数

在部署前，您可以通过编辑 `config.yaml` 文件来配置部署参数：

```yaml
# 前端部署配置

# 服务器配置
server:
  # 部署的服务器地址
  host: localhost
  # 部署的服务器端口
  port: 8080

# API配置
api:
  # 后端API地址
  base_url: http://localhost:5001
  # API超时时间（毫秒）
  timeout: 10000

# 构建配置
build:
  # 构建模式: development, production
  mode: production
  # 构建输出目录
  output_dir: dist
```

### 3. 执行部署脚本

执行部署脚本以安装依赖并构建项目：

```bash
./deploy.sh
```

脚本会自动：
- 检查并创建配置文件（如果不存在）
- 安装项目依赖
- 构建项目

### 4. 部署到Web服务器

构建完成后，将 `dist` 目录部署到您的Web服务器上：

- **Nginx** 示例配置：
  ```nginx
  server {
    listen 80;
    server_name example.com;
    
    root /path/to/frontend/dist;
    index index.html;
    
    location / {
      try_files $uri $uri/ /index.html;
    }
  }
  ```

- **Apache** 示例配置：
  ```apache
  <VirtualHost *:80>
    ServerName example.com
    DocumentRoot /path/to/frontend/dist
    
    <Directory /path/to/frontend/dist>
      AllowOverride All
      Require all granted
    </Directory>
  </VirtualHost>
  ```

## 配置说明

### 服务器配置

- `server.host`：部署的服务器地址
- `server.port`：部署的服务器端口

### API配置

- `api.base_url`：后端API地址，确保与后端服务地址一致
- `api.timeout`：API请求超时时间（毫秒）

### 构建配置

- `build.mode`：构建模式，生产环境使用 `production`
- `build.output_dir`：构建输出目录

## 常见问题

### 1. 构建失败

- 检查Node.js和npm版本是否符合要求
- 检查网络连接是否正常，确保能正常下载依赖

### 2. 前端无法连接后端API

- 检查 `config.yaml` 中的 `api.base_url` 是否正确配置
- 检查后端服务是否正常运行
- 检查网络连接和防火墙设置

### 3. 页面刷新后404

- 确保Web服务器配置了正确的路由重写规则，将所有请求指向 `index.html`

## 开发模式运行

如果您需要在开发模式下运行项目：

```bash
npm run dev
```

项目将在 `http://localhost:5173` 上运行。
