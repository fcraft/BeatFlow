#!/usr/bin/env bash
#
# BeatFlow 本地开发服务状态检查 & 自动启动脚本
#
# 检查以下服务并在未运行时自动启动：
#   1. PostgreSQL  (port 5432)
#   2. Backend     (uvicorn, port 3090)
#   3. Frontend    (vite dev, port 3080)
#
# 用法:
#   ./scripts/dev-check.sh          # 检查并启动所有服务
#   ./scripts/dev-check.sh status   # 仅查看状态，不启动
#   ./scripts/dev-check.sh stop     # 停止由本脚本启动的服务
#

set -euo pipefail

# ─── 项目路径 ────────────────────────────────────────────────────────────────
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# ─── 颜色 ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# ─── 配置 ────────────────────────────────────────────────────────────────────
POSTGRES_PORT=5432
BACKEND_PORT=3090
FRONTEND_PORT=3080

BACKEND_VENV="$BACKEND_DIR/.venv"
BACKEND_LOG="$PROJECT_ROOT/logs/backend.log"
FRONTEND_LOG="$PROJECT_ROOT/logs/frontend.log"
PID_DIR="$PROJECT_ROOT/.dev-pids"

# ─── 工具函数 ────────────────────────────────────────────────────────────────

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()      { echo -e "${GREEN}[  OK]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()    { echo -e "${RED}[FAIL]${NC}  $*"; }
header()  { echo -e "\n${BOLD}${CYAN}═══ $* ═══${NC}"; }

# 检查端口是否被监听
port_listening() {
    ss -tlnp 2>/dev/null | grep -q ":${1}\b" 2>/dev/null
}

# 检查进程是否存在
pid_alive() {
    [ -n "$1" ] && kill -0 "$1" 2>/dev/null
}

# 等待端口就绪
wait_for_port() {
    local port=$1 name=$2 timeout=${3:-30}
    local elapsed=0
    while ! port_listening "$port"; do
        sleep 1
        elapsed=$((elapsed + 1))
        if [ "$elapsed" -ge "$timeout" ]; then
            fail "$name 在 ${timeout}s 内未能启动 (port $port)"
            return 1
        fi
    done
    return 0
}

# 确保目录存在
ensure_dirs() {
    mkdir -p "$PROJECT_ROOT/logs" "$PID_DIR"
}

# ─── PostgreSQL ──────────────────────────────────────────────────────────────

check_postgres() {
    if port_listening $POSTGRES_PORT; then
        ok "PostgreSQL 正在运行 (port $POSTGRES_PORT)"
        # 尝试连接验证
        if command -v psql &>/dev/null; then
            if PGPASSWORD=beat_flow_password psql -U beat_flow_user -d beat_flow -h localhost -p $POSTGRES_PORT -c "SELECT 1;" &>/dev/null; then
                ok "PostgreSQL 连接验证通过 (beat_flow 数据库)"
            else
                warn "PostgreSQL 端口开放，但无法连接 beat_flow 数据库"
            fi
        fi
        return 0
    else
        fail "PostgreSQL 未运行 (port $POSTGRES_PORT)"
        return 1
    fi
}

start_postgres() {
    if check_postgres; then return 0; fi

    info "尝试启动 PostgreSQL..."

    # 方式1: systemctl (本机安装)
    if command -v systemctl &>/dev/null; then
        if systemctl start postgresql 2>/dev/null; then
            wait_for_port $POSTGRES_PORT "PostgreSQL" 15 && ok "PostgreSQL 已通过 systemctl 启动" && return 0
        fi
    fi

    # 方式2: Docker
    if command -v docker &>/dev/null; then
        local pg_container="beat-flow-postgres"
        if docker ps -a --format '{{.Names}}' | grep -q "^${pg_container}$"; then
            docker start "$pg_container" &>/dev/null
        else
            info "创建 PostgreSQL Docker 容器..."
            docker run -d \
                --name "$pg_container" \
                -e POSTGRES_DB=beat_flow \
                -e POSTGRES_USER=beat_flow_user \
                -e POSTGRES_PASSWORD=beat_flow_password \
                -p ${POSTGRES_PORT}:5432 \
                -v beat-flow-postgres-data:/var/lib/postgresql/data \
                postgres:15-alpine &>/dev/null
        fi
        wait_for_port $POSTGRES_PORT "PostgreSQL" 20 && ok "PostgreSQL 已通过 Docker 启动" && return 0
    fi

    fail "无法启动 PostgreSQL，请手动安装或配置 Docker"
    return 1
}

# ─── Backend (FastAPI + Uvicorn) ─────────────────────────────────────────────

check_backend() {
    # 检查端口 + 确认是 uvicorn 进程
    if port_listening $BACKEND_PORT; then
        local pid
        pid=$(ss -tlnp 2>/dev/null | grep ":${BACKEND_PORT}\b" | grep -oP 'pid=\K[0-9]+' | head -1)
        if [ -n "$pid" ]; then
            local cmdline
            cmdline=$(ps -p "$pid" -o cmd= 2>/dev/null || echo "")
            if echo "$cmdline" | grep -qE '(uvicorn|python)'; then
                ok "Backend (uvicorn) 正在运行 (port $BACKEND_PORT, PID $pid)"
                return 0
            else
                warn "端口 $BACKEND_PORT 被其他进程占用: $cmdline"
                return 2
            fi
        fi
        ok "Backend 端口 $BACKEND_PORT 已被监听"
        return 0
    else
        fail "Backend 未运行 (port $BACKEND_PORT)"
        return 1
    fi
}

start_backend() {
    local status
    check_backend
    status=$?

    case $status in
        0) return 0 ;;
        2)
            warn "端口 $BACKEND_PORT 被占用，无法启动 Backend"
            warn "请先释放端口或修改 backend/.env 中的 PORT 配置"
            return 1
            ;;
    esac

    info "启动 Backend (uvicorn)..."

    # 检查 venv
    if [ ! -f "$BACKEND_VENV/bin/uvicorn" ]; then
        fail "未找到 Backend venv ($BACKEND_VENV/bin/uvicorn)"
        info "请先执行: cd $BACKEND_DIR && uv sync"
        return 1
    fi

    ensure_dirs

    # 启动 uvicorn (后台, 带 reload)
    cd "$BACKEND_DIR"
    nohup "$BACKEND_VENV/bin/uvicorn" app.main:app \
        --reload \
        --host 0.0.0.0 \
        --port $BACKEND_PORT \
        > "$BACKEND_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_DIR/backend.pid"
    cd "$PROJECT_ROOT"

    wait_for_port $BACKEND_PORT "Backend" 20 && ok "Backend 已启动 (PID $pid, 日志: $BACKEND_LOG)" && return 0

    fail "Backend 启动失败，请查看日志: $BACKEND_LOG"
    return 1
}

# ─── Frontend (Vite Dev Server) ──────────────────────────────────────────────

check_frontend() {
    if port_listening $FRONTEND_PORT; then
        local pid
        pid=$(ss -tlnp 2>/dev/null | grep ":${FRONTEND_PORT}\b" | grep -oP 'pid=\K[0-9]+' | head -1)
        if [ -n "$pid" ]; then
            ok "Frontend (Vite) 正在运行 (port $FRONTEND_PORT, PID $pid)"
        else
            ok "Frontend 端口 $FRONTEND_PORT 已被监听"
        fi
        return 0
    else
        fail "Frontend 未运行 (port $FRONTEND_PORT)"
        return 1
    fi
}

start_frontend() {
    if check_frontend; then return 0; fi

    info "启动 Frontend (Vite dev server)..."

    # 检查 node_modules
    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        info "安装前端依赖..."
        if command -v pnpm &>/dev/null; then
            (cd "$FRONTEND_DIR" && pnpm install --frozen-lockfile 2>/dev/null || pnpm install)
        else
            (cd "$FRONTEND_DIR" && npm install)
        fi
    fi

    ensure_dirs

    # 启动 vite dev server (后台)
    cd "$FRONTEND_DIR"
    nohup npm run dev > "$FRONTEND_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_DIR/frontend.pid"
    cd "$PROJECT_ROOT"

    wait_for_port $FRONTEND_PORT "Frontend" 30 && ok "Frontend 已启动 (PID $pid, 日志: $FRONTEND_LOG)" && return 0

    fail "Frontend 启动失败，请查看日志: $FRONTEND_LOG"
    return 1
}

# ─── 停止服务 ────────────────────────────────────────────────────────────────

stop_services() {
    header "停止 BeatFlow 开发服务"

    # 停止 Backend
    if [ -f "$PID_DIR/backend.pid" ]; then
        local bpid
        bpid=$(cat "$PID_DIR/backend.pid")
        if pid_alive "$bpid"; then
            kill "$bpid" 2>/dev/null && ok "Backend 已停止 (PID $bpid)"
            # 同时 kill 子进程 (uvicorn reload spawns children)
            pkill -P "$bpid" 2>/dev/null || true
        else
            info "Backend 进程 (PID $bpid) 已不存在"
        fi
        rm -f "$PID_DIR/backend.pid"
    else
        info "未找到 Backend PID 文件"
    fi

    # 停止 Frontend
    if [ -f "$PID_DIR/frontend.pid" ]; then
        local fpid
        fpid=$(cat "$PID_DIR/frontend.pid")
        if pid_alive "$fpid"; then
            kill "$fpid" 2>/dev/null && ok "Frontend 已停止 (PID $fpid)"
            pkill -P "$fpid" 2>/dev/null || true
        else
            info "Frontend 进程 (PID $fpid) 已不存在"
        fi
        rm -f "$PID_DIR/frontend.pid"
    else
        info "未找到 Frontend PID 文件"
    fi

    info "PostgreSQL 由系统管理，未执行停止操作"
    echo ""
    ok "所有可停止的服务已处理完毕"
}

# ─── 状态总览 ────────────────────────────────────────────────────────────────

show_status() {
    header "BeatFlow 开发服务状态"
    echo ""

    local all_ok=true

    check_postgres  || all_ok=false
    echo ""
    check_backend   || all_ok=false
    echo ""
    check_frontend  || all_ok=false

    echo ""
    echo -e "${BOLD}────────────────────────────────────────${NC}"
    if $all_ok; then
        ok "${BOLD}所有服务运行正常${NC}"
    else
        warn "${BOLD}部分服务未运行，执行 $0 启动所有服务${NC}"
    fi
    echo ""
}

# ─── 启动全部 ────────────────────────────────────────────────────────────────

start_all() {
    header "BeatFlow 开发服务检查 & 启动"
    echo ""
    echo -e "${CYAN}项目目录: $PROJECT_ROOT${NC}"
    echo ""

    local failed=0

    echo -e "${BOLD}[1/3] PostgreSQL${NC}"
    start_postgres || ((failed++))
    echo ""

    echo -e "${BOLD}[2/3] Backend (FastAPI)${NC}"
    start_backend || ((failed++))
    echo ""

    echo -e "${BOLD}[3/3] Frontend (Vite)${NC}"
    start_frontend || ((failed++))
    echo ""

    # ─── 总结 ────────────────────────────────────────────────────────
    echo -e "${BOLD}${CYAN}═══ 服务总览 ═══${NC}"
    echo ""

    local summary=""
    summary+="  PostgreSQL   : $(port_listening $POSTGRES_PORT && echo -e "${GREEN}运行中${NC} (port $POSTGRES_PORT)" || echo -e "${RED}未运行${NC}")\n"
    summary+="  Backend      : $(port_listening $BACKEND_PORT && echo -e "${GREEN}运行中${NC} (port $BACKEND_PORT)" || echo -e "${RED}未运行${NC}")\n"
    summary+="  Frontend     : $(port_listening $FRONTEND_PORT && echo -e "${GREEN}运行中${NC} (port $FRONTEND_PORT)" || echo -e "${RED}未运行${NC}")\n"
    echo -e "$summary"

    if [ "$failed" -eq 0 ]; then
        echo -e "${GREEN}${BOLD}所有服务已就绪!${NC}"
        echo ""
        echo -e "  Frontend : ${CYAN}https://localhost:${FRONTEND_PORT}${NC}"
        echo -e "  Backend  : ${CYAN}http://localhost:${BACKEND_PORT}${NC}"
        echo -e "  API Docs : ${CYAN}http://localhost:${BACKEND_PORT}/docs${NC}"
    else
        echo -e "${YELLOW}${BOLD}有 $failed 个服务启动失败，请检查上方日志${NC}"
    fi
    echo ""
}

# ─── 主入口 ──────────────────────────────────────────────────────────────────

case "${1:-}" in
    status|s)
        show_status
        ;;
    stop)
        stop_services
        ;;
    help|-h|--help)
        echo "用法: $0 [command]"
        echo ""
        echo "命令:"
        echo "  (无参数)   检查并启动所有服务"
        echo "  status     仅查看服务状态"
        echo "  stop       停止由本脚本启动的服务"
        echo "  help       显示帮助信息"
        ;;
    *)
        start_all
        ;;
esac
