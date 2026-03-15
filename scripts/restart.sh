#!/usr/bin/env bash
#
# BeatFlow 开发服务重启脚本
#
# 用法:
#   ./scripts/restart.sh              # 重启 Backend + Frontend（最常用）
#   ./scripts/restart.sh all          # 重启所有服务（含 PostgreSQL）
#   ./scripts/restart.sh backend      # 仅重启 Backend
#   ./scripts/restart.sh frontend     # 仅重启 Frontend
#   ./scripts/restart.sh backend frontend   # 重启指定的多个服务
#
# 支持的服务名:
#   backend / be    — FastAPI (uvicorn)
#   frontend / fe   — Vite dev server
#   postgres / pg   — PostgreSQL
#   all             — 以上全部
#

set -euo pipefail

# ─── 项目路径 ────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEV_CHECK="$SCRIPT_DIR/dev-check.sh"

BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
BACKEND_PORT=3090
FRONTEND_PORT=3080
POSTGRES_PORT=5432
BACKEND_VENV="$BACKEND_DIR/.venv"
BACKEND_LOG="$PROJECT_ROOT/logs/backend.log"
FRONTEND_LOG="$PROJECT_ROOT/logs/frontend.log"
PID_DIR="$PROJECT_ROOT/.dev-pids"

# ─── 颜色 ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()      { echo -e "${GREEN}[  OK]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()    { echo -e "${RED}[FAIL]${NC}  $*"; }
header()  { echo -e "\n${BOLD}${CYAN}═══ $* ═══${NC}"; }

port_listening() {
    ss -tlnp 2>/dev/null | grep -q ":${1}\b" 2>/dev/null
}

pid_alive() {
    [ -n "$1" ] && kill -0 "$1" 2>/dev/null
}

# ─── 停止单个服务 ─────────────────────────────────────────────────────────────

stop_backend() {
    info "停止 Backend..."

    if [ -f "$PID_DIR/backend.pid" ]; then
        local bpid
        bpid=$(cat "$PID_DIR/backend.pid")
        if pid_alive "$bpid"; then
            kill "$bpid" 2>/dev/null
            pkill -P "$bpid" 2>/dev/null || true
            ok "Backend 已停止 (PID $bpid)"
        fi
        rm -f "$PID_DIR/backend.pid"
    fi

    local pids
    pids=$(ss -tlnp 2>/dev/null | grep ":${BACKEND_PORT}\b" | grep -oP 'pid=\K[0-9]+' || true)
    for p in $pids; do
        if pid_alive "$p"; then
            kill "$p" 2>/dev/null || true
            pkill -P "$p" 2>/dev/null || true
        fi
    done

    local waited=0
    while port_listening $BACKEND_PORT && [ "$waited" -lt 10 ]; do
        sleep 1
        waited=$((waited + 1))
    done

    if port_listening $BACKEND_PORT; then
        warn "Backend 端口 $BACKEND_PORT 仍被占用，尝试强制终止..."
        pids=$(ss -tlnp 2>/dev/null | grep ":${BACKEND_PORT}\b" | grep -oP 'pid=\K[0-9]+' || true)
        for p in $pids; do kill -9 "$p" 2>/dev/null || true; done
        sleep 1
    fi
}

stop_frontend() {
    info "停止 Frontend..."

    if [ -f "$PID_DIR/frontend.pid" ]; then
        local fpid
        fpid=$(cat "$PID_DIR/frontend.pid")
        if pid_alive "$fpid"; then
            kill "$fpid" 2>/dev/null
            pkill -P "$fpid" 2>/dev/null || true
            ok "Frontend 已停止 (PID $fpid)"
        fi
        rm -f "$PID_DIR/frontend.pid"
    fi

    local pids
    pids=$(ss -tlnp 2>/dev/null | grep ":${FRONTEND_PORT}\b" | grep -oP 'pid=\K[0-9]+' || true)
    for p in $pids; do
        if pid_alive "$p"; then
            kill "$p" 2>/dev/null || true
            pkill -P "$p" 2>/dev/null || true
        fi
    done

    local waited=0
    while port_listening $FRONTEND_PORT && [ "$waited" -lt 10 ]; do
        sleep 1
        waited=$((waited + 1))
    done

    if port_listening $FRONTEND_PORT; then
        warn "Frontend 端口 $FRONTEND_PORT 仍被占用，尝试强制终止..."
        pids=$(ss -tlnp 2>/dev/null | grep ":${FRONTEND_PORT}\b" | grep -oP 'pid=\K[0-9]+' || true)
        for p in $pids; do kill -9 "$p" 2>/dev/null || true; done
        sleep 1
    fi
}

stop_postgres() {
    info "停止 PostgreSQL..."
    if command -v systemctl &>/dev/null; then
        if systemctl is-active --quiet postgresql 2>/dev/null; then
            systemctl stop postgresql 2>/dev/null && ok "PostgreSQL 已通过 systemctl 停止" && return 0
        fi
    fi
    if command -v docker &>/dev/null; then
        local pg_container="beat-flow-postgres"
        if docker ps --format '{{.Names}}' | grep -q "^${pg_container}$"; then
            docker stop "$pg_container" &>/dev/null && ok "PostgreSQL Docker 容器已停止" && return 0
        fi
    fi
    warn "PostgreSQL 未在运行或由外部管理，跳过"
}

# ─── 启动单个服务 ─────────────────────────────────────────────────────────────

start_backend() {
    info "启动 Backend (uvicorn)..."

    if port_listening $BACKEND_PORT; then
        ok "Backend 已在运行 (port $BACKEND_PORT)"
        return 0
    fi

    if [ ! -f "$BACKEND_VENV/bin/uvicorn" ]; then
        fail "未找到 Backend venv ($BACKEND_VENV/bin/uvicorn)"
        return 1
    fi

    mkdir -p "$PROJECT_ROOT/logs" "$PID_DIR"

    export PIPELINE_VERSION="${PIPELINE_VERSION:-v2}"
    info "引擎版本: PIPELINE_VERSION=$PIPELINE_VERSION"

    cd "$BACKEND_DIR"
    nohup "$BACKEND_VENV/bin/uvicorn" app.main:app \
        --reload \
        --host 0.0.0.0 \
        --port $BACKEND_PORT \
        > "$BACKEND_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_DIR/backend.pid"
    cd "$PROJECT_ROOT"

    local elapsed=0
    while ! port_listening $BACKEND_PORT; do
        sleep 1
        elapsed=$((elapsed + 1))
        if [ "$elapsed" -ge 20 ]; then
            fail "Backend 在 20s 内未能启动，请查看日志: $BACKEND_LOG"
            return 1
        fi
    done
    ok "Backend 已启动 (PID $pid, port $BACKEND_PORT)"
    echo -e "  日志: ${CYAN}$BACKEND_LOG${NC}"
}

start_frontend() {
    info "启动 Frontend (Vite dev server)..."

    if port_listening $FRONTEND_PORT; then
        ok "Frontend 已在运行 (port $FRONTEND_PORT)"
        return 0
    fi

    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        info "安装前端依赖..."
        (cd "$FRONTEND_DIR" && pnpm install --frozen-lockfile 2>/dev/null || pnpm install)
    fi

    mkdir -p "$PROJECT_ROOT/logs" "$PID_DIR"

    cd "$FRONTEND_DIR"
    nohup pnpm dev > "$FRONTEND_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_DIR/frontend.pid"
    cd "$PROJECT_ROOT"

    local elapsed=0
    while ! port_listening $FRONTEND_PORT; do
        sleep 1
        elapsed=$((elapsed + 1))
        if [ "$elapsed" -ge 30 ]; then
            fail "Frontend 在 30s 内未能启动，请查看日志: $FRONTEND_LOG"
            return 1
        fi
    done
    ok "Frontend 已启动 (PID $pid, port $FRONTEND_PORT)"
    echo -e "  日志: ${CYAN}$FRONTEND_LOG${NC}"
}

start_postgres() {
    if port_listening $POSTGRES_PORT; then
        ok "PostgreSQL 已在运行 (port $POSTGRES_PORT)"
        return 0
    fi
    if command -v systemctl &>/dev/null; then
        systemctl start postgresql 2>/dev/null && sleep 2
    fi
    if command -v docker &>/dev/null && ! port_listening $POSTGRES_PORT; then
        docker start beat-flow-postgres 2>/dev/null || true
        sleep 3
    fi
    port_listening $POSTGRES_PORT && ok "PostgreSQL 已启动 (port $POSTGRES_PORT)" || fail "PostgreSQL 启动失败"
}

# ─── 重启编排 ─────────────────────────────────────────────────────────────────

restart_service() {
    local svc="$1"
    case "$svc" in
        backend|be)
            stop_backend
            start_backend
            ;;
        frontend|fe)
            stop_frontend
            start_frontend
            ;;
        postgres|pg)
            stop_postgres
            start_postgres
            ;;
        *)
            fail "未知服务: $svc"
            echo "  支持: backend(be) | frontend(fe) | postgres(pg) | all"
            return 1
            ;;
    esac
}

# ─── 显示总览 ─────────────────────────────────────────────────────────────────

show_summary() {
    echo ""
    echo -e "${BOLD}${CYAN}═══ 重启后服务总览 ═══${NC}"
    echo ""
    echo -e "  PostgreSQL : $(port_listening $POSTGRES_PORT && echo -e "${GREEN}运行中${NC} (port $POSTGRES_PORT)" || echo -e "${RED}未运行${NC}")"
    echo -e "  Backend    : $(port_listening $BACKEND_PORT && echo -e "${GREEN}运行中${NC} (port $BACKEND_PORT)" || echo -e "${RED}未运行${NC}")"
    echo -e "  Frontend   : $(port_listening $FRONTEND_PORT && echo -e "${GREEN}运行中${NC} (port $FRONTEND_PORT)" || echo -e "${RED}未运行${NC}")"
    echo ""
    if port_listening $FRONTEND_PORT; then
        echo -e "  Frontend : ${CYAN}https://localhost:${FRONTEND_PORT}${NC}"
    fi
    if port_listening $BACKEND_PORT; then
        echo -e "  Backend  : ${CYAN}http://localhost:${BACKEND_PORT}${NC}"
        echo -e "  API Docs : ${CYAN}http://localhost:${BACKEND_PORT}/docs${NC}"
    fi
    echo ""
}

# ─── 主入口 ──────────────────────────────────────────────────────────────────

main() {
    local args=("$@")

    header "BeatFlow 服务重启"
    echo -e "${CYAN}项目目录: $PROJECT_ROOT${NC}"

    if [ ${#args[@]} -eq 0 ]; then
        info "默认重启 Backend + Frontend"
        echo ""
        restart_service backend
        echo ""
        restart_service frontend
        show_summary
        return 0
    fi

    case "${args[0]}" in
        help|-h|--help)
            echo "用法: $0 [服务名...]"
            echo ""
            echo "服务名:"
            echo "  (无参数)          重启 Backend + Frontend（最常用）"
            echo "  all               重启所有服务"
            echo "  backend / be      仅重启 Backend"
            echo "  frontend / fe     仅重启 Frontend"
            echo "  postgres / pg     仅重启 PostgreSQL"
            echo ""
            echo "可组合多个服务:"
            echo "  $0 backend frontend   重启 Backend 和 Frontend"
            echo ""
            echo "关联脚本:"
            echo "  ./scripts/dev-check.sh          检查并启动所有服务"
            echo "  ./scripts/dev-check.sh status   仅查看状态"
            echo "  ./scripts/dev-check.sh stop     停止所有服务"
            return 0
            ;;
        all)
            info "重启所有服务"
            echo ""
            stop_backend
            stop_frontend
            stop_postgres
            echo ""
            info "所有服务已停止，开始启动..."
            echo ""
            start_postgres
            echo ""
            start_backend
            echo ""
            start_frontend
            show_summary
            return 0
            ;;
    esac

    local failed=0
    for svc in "${args[@]}"; do
        echo ""
        restart_service "$svc" || ((failed++))
    done

    show_summary

    if [ "$failed" -gt 0 ]; then
        warn "$failed 个服务重启失败"
        return 1
    fi

    ok "${BOLD}所有指定服务已重启完毕${NC}"
}

main "$@"
