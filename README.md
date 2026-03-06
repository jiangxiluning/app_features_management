# 项目名称

一个完整的前后端分离应用，包含后端 API 服务和前端管理界面。

## 项目描述

本项目是一个功能完整的现代化应用管理系统，旨在为企业和组织提供高效、安全、易用的管理解决方案。系统采用前后端分离架构，后端基于 Python Flask 框架提供稳定的 API 服务，前端使用 Vue.js 构建响应式用户界面。

### 核心价值

- **一站式管理**：集成用户管理、设备监控、审计日志、数据备份等多种功能，满足企业日常管理需求
- **安全可靠**：完善的权限控制和审计机制，确保系统操作可追溯，数据安全有保障
- **易于扩展**：模块化设计使得系统可以根据业务需求灵活扩展功能
- **用户友好**：直观的界面设计和流畅的操作体验，降低使用门槛

## 功能特性

- **后端服务**：基于 Python 的 API 服务，提供数据管理和业务逻辑
- **前端界面**：基于 Vue.js 的现代化管理界面
- **用户管理**：用户注册、登录和权限控制
- **设备管理**：设备信息管理和状态监控
- **审计日志**：操作审计和日志记录
- **数据备份**：定期数据备份功能
- **统计分析**：数据统计和可视化展示

## 技术栈

### 后端
- Python
- Flask
- SQLite

### 前端
- Vue.js
- Vite
- Vue Router

## 快速开始

### 后端部署

1. 进入后端目录
   ```bash
   cd backend
   ```

2. 安装依赖
   ```bash
   pip install -r requirements.txt
   ```

3. 启动服务
   ```bash
   python app.py
   ```

### 前端部署

1. 进入前端目录
   ```bash
   cd frontend
   ```

2. 安装依赖
   ```bash
   npm install
   ```

3. 启动开发服务器
   ```bash
   npm run dev
   ```

4. 构建生产版本
   ```bash
   npm run build
   ```

## 项目结构

```
├── backend/          # 后端代码
│   ├── app.py        # 主应用入口
│   ├── config.yaml   # 配置文件
│   ├── requirements.txt  # 依赖包
│   └── deploy.sh     # 部署脚本
├── frontend/         # 前端代码
│   ├── src/          # 源代码
│   │   ├── views/    # 页面组件
│   │   ├── api/      # API 调用
│   │   └── router/   # 路由配置
│   ├── package.json  # 项目配置
│   └── vite.config.js  # Vite 配置
├── .gitignore        # Git 忽略文件
└── README.md         # 项目说明
```

## 许可证

本项目使用 Apache 许可证 2.0 版本。详情请参阅 [LICENSE](LICENSE) 文件。

## 贡献

欢迎提交 Issue 和 Pull Request 来帮助改进这个项目。

## 联系方式

如有问题或建议，请通过 GitHub Issues 与我们联系。