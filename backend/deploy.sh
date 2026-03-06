#!/bin/bash

# 后端部署脚本

# 颜色定义
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m" # No Color

echo -e "${GREEN}=== 后端部署脚本 ===${NC}"

# 检查配置文件是否存在
if [ ! -f "config.yaml" ]; then
  echo -e "${YELLOW}配置文件 config.yaml 不存在，使用默认配置${NC}"
  # 创建默认配置文件
  cat > config.yaml << EOF
# 后端服务器配置
server:
  host: 0.0.0.0
  port: 5001

# 备份配置
backup:
  path: ./backups
  interval: 1
  keep_latest: 10
  enabled: true
EOF
  echo -e "${GREEN}已创建默认配置文件 config.yaml${NC}"
fi

# 确保备份目录存在
mkdir -p backups

# 安装依赖
echo -e "${GREEN}正在安装依赖...${NC}"
pip3 install -r requirements.txt
if [ $? -ne 0 ]; then
  echo -e "${RED}依赖安装失败${NC}"
  exit 1
fi

echo -e "${GREEN}=== 部署完成 ===${NC}"
echo -e "${GREEN}后端依赖安装成功${NC}"
echo -e "${YELLOW}提示: 运行以下命令启动后端服务:${NC}"
echo -e "${YELLOW}python3 app.py${NC}"
