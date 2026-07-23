# start.ps1 - Windows PowerShell 启动脚本
$ErrorActionPreference = "Stop"
Write-Host "🚀 Starting Doc-Agent..." -ForegroundColor Cyan

# 检查 Python 版本
try {
    python --version
} catch {
    Write-Host "Python 3.9+ required" -ForegroundColor Red
    exit 1
}

# 安装依赖
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install -e .

# 初始化工作区
try {
    doc-agent init
} catch {
    # 忽略初始化错误
}

# 构建前端（如果 dist 不存在）
if (-not (Test-Path "frontend/dist")) {
    Write-Host "Building frontend..." -ForegroundColor Yellow
    Push-Location frontend
    npm install
    npm run build
    Pop-Location
}

# 启动服务
doc-agent serve
