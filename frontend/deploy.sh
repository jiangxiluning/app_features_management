#!/bin/bash

# 前端部署脚本

# 颜色定义
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m" # No Color

echo -e "${GREEN}=== 前端部署脚本 ===${NC}"

# 检查配置文件是否存在
if [ ! -f "config.yaml" ]; then
  echo -e "${YELLOW}配置文件 config.yaml 不存在，使用默认配置${NC}"
  # 创建默认配置文件
  cat > config.yaml << EOF
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
EOF
  echo -e "${GREEN}已创建默认配置文件 config.yaml${NC}"
fi

# 安装依赖
echo -e "${GREEN}正在安装依赖...${NC}"
npm install
if [ $? -ne 0 ]; then
  echo -e "${RED}依赖安装失败${NC}"
  exit 1
fi

# 构建项目
echo -e "${GREEN}正在构建项目...${NC}"
npm run build
if [ $? -ne 0 ]; then
  echo -e "${RED}项目构建失败${NC}"
  exit 1
fi

echo -e "${GREEN}=== 部署完成 ===${NC}"
echo -e "${GREEN}前端项目已构建成功，输出目录: dist${NC}"
echo -e "${YELLOW}提示: 请将 dist 目录部署到您的Web服务器上${NC}"
