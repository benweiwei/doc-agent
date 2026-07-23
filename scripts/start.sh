#!/bin/bash
set -e
echo "🚀 Starting Doc-Agent..."

# 检查 Python 版本
python3 --version || { echo "Python 3.9+ required"; exit 1; }

# 安装依赖（如果未安装）
pip install -e . 2>/dev/null || pip install -e .

# 初始化工作区
doc-agent init 2>/dev/null || true

# 构建前端（如果 dist 不存在）
if [ ! -d "frontend/dist" ]; then
  echo "Building frontend..."
  cd frontend && npm install && npm run build && cd ..
fi

# 启动服务
doc-agent serve
