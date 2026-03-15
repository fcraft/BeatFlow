#!/bin/bash

# BeatFlow 安装脚本
# 本脚本用于设置开发环境和数据库初始化

set -e

echo "🚀 开始安装 BeatFlow..."

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose 未安装，请先安装 Docker Compose"
    exit 1
fi

# 检查Node.js
if ! command -v node &> /dev/null; then
    echo "⚠️  Node.js 未安装，将跳过前端依赖安装"
fi

if ! command -v npm &> /dev/null; then
    echo "⚠️  npm 未安装，将跳过前端依赖安装"
fi

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装，请先安装 Python3"
    exit 1
fi

# 检查uv
if ! command -v uv &> /dev/null; then
    echo "🔧 安装 uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# 创建环境配置文件
echo "📝 创建环境配置文件..."

# 后端 .env 文件
if [ ! -f backend/.env ]; then
    cat > backend/.env << EOF
# 应用配置
APP_ENV=development
APP_DEBUG=true
APP_SECRET_KEY=$(openssl rand -hex 32)

# 数据库配置
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/beat_flow
DATABASE_POOL_SIZE=10

# JWT配置
JWT_SECRET_KEY=$(openssl rand -hex 32)
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=120
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# 文件存储
STORAGE_TYPE=local
UPLOAD_DIR=./uploads
MAX_FILE_SIZE_MB=512

# CORS配置
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
ALLOWED_HOSTS=["localhost","127.0.0.1"]

# 其他配置
LOG_LEVEL=INFO
RATE_LIMIT_ENABLED=false
EOF
    echo "✅ 后端 .env 文件已创建"
else
    echo "ℹ️  后端 .env 文件已存在"
fi

# 前端 .env 文件
if [ ! -f frontend/.env.local ]; then
    cat > frontend/.env.local << EOF
# 前端配置
VITE_API_URL=http://localhost:3090
VITE_APP_NAME=BeatFlow
VITE_APP_VERSION=0.1.0
VITE_SOCKET_URL=ws://localhost:3090/ws
EOF
    echo "✅ 前端 .env.local 文件已创建"
else
    echo "ℹ️  前端 .env.local 文件已存在"
fi

# 创建必需的目录
echo "📁 创建目录结构..."
mkdir -p backend/uploads backend/storage frontend/public

# 安装后端依赖
echo "📦 安装后端依赖..."
cd backend
uv sync --frozen
echo "✅ 后端依赖安装完成"
cd ..

# 安装前端依赖
echo "📦 安装前端依赖..."
if command -v npm &> /dev/null; then
    cd frontend
    if [ ! -d node_modules ]; then
        npm install
        echo "✅ 前端依赖安装完成"
    else
        echo "ℹ️  前端依赖已安装（node_modules存在）"
    fi
    cd ..
else
    echo "⚠️  跳过前端依赖安装（npm不可用）"
fi

# 启动Docker服务
echo "🐳 启动 Docker 服务..."
docker-compose up -d

# 等待数据库就绪
echo "⏳ 等待数据库就绪..."
sleep 10

# 运行数据库迁移
echo "🗄️  运行数据库迁移..."
cd backend
uv run python -c "
from app.db.session import init_db
import asyncio
asyncio.run(init_db())
"
echo "✅ 数据库迁移完成"
cd ..

# 创建默认用户
echo "👤 创建默认用户..."
cat > /tmp/create_user.py << 'EOF'
#!/usr/bin/env python3
import asyncio
import sys
sys.path.append('./backend')

from app.db.session import db_manager
from app.crud.user import user_crud
from app.models.user import UserCreate

async def create_default_users():
    async with db_manager.async_session_factory() as db:
        # 检查是否已有用户
        existing = await user_crud.get_by_username(db, "admin")
        if existing:
            print("管理员用户已存在")
            return
        
        # 创建管理员用户
        admin_user = UserCreate(
            username="admin",
            email="admin@example.com",
            full_name="系统管理员",
            password="Admin123!",
        )
        await user_crud.create(db, admin_user)
        print("✅ 管理员用户创建成功")
        print("   用户名: admin")
        print("   密码: Admin123!")
        print("   邮箱: admin@example.com")
        
        # 创建测试用户
        test_user = UserCreate(
            username="testuser",
            email="user@example.com",
            full_name="测试用户",
            password="Test123!",
        )
        await user_crud.create(db, test_user)
        print("✅ 测试用户创建成功")
        print("   用户名: testuser")
        print("   密码: Test123!")

if __name__ == "__main__":
    asyncio.run(create_default_users())
EOF

cd backend
uv run python /tmp/create_user.py
rm /tmp/create_user.py
cd ..

echo ""
echo "🎉 安装完成!"
echo ""
echo "🔗 服务地址:"
echo "   前端: http://localhost:3000"
echo "   后端API: http://localhost:3090"
echo "   API文档: http://localhost:3090/docs"
echo ""
echo "🔑 默认用户:"
echo "   管理员: admin / Admin123!"
echo "   测试用户: testuser / Test123!"
echo ""
echo "🛠️  命令说明:"
echo "   启动所有服务: docker-compose up -d"
echo "   停止服务: docker-compose down"
echo "   查看日志: docker-compose logs -f"
echo "   后端开发: cd backend && uv run uvicorn app.main:app --reload"
echo "   前端开发: cd frontend && npm run dev"
echo ""
echo "📋 下一步:"
echo "   1. 访问 http://localhost:3000 打开前端界面"
echo "   2. 使用默认用户登录"
echo "   3. 创建一个测试项目并上传文件"
echo ""