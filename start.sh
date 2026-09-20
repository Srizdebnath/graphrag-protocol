#!/usr/bin/env bash
# ==============================================================================
# GraphRAG Protocol — Solo Startup Script
#
# Launches both the FastAPI backend (port 8000) and Next.js frontend (port 3000).
# Handles graceful shutdown on Ctrl+C.
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for terminal output
BOLD="\033[1m"
GREEN="\033[0;32m"
BLUE="\033[0;34m"
CYAN="\033[0;36m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
RESET="\033[0m"

echo -e "${BOLD}${CYAN}================================================================${RESET}"
echo -e "${BOLD}${CYAN}           GraphRAG Protocol — Universal Startup Script         ${RESET}"
echo -e "${BOLD}${CYAN}================================================================${RESET}"

# 1. Check Python environment
if [ ! -f ".venv/bin/python" ]; then
    echo -e "${RED}[!] Virtual environment not found at .venv${RESET}"
    echo -e "    Please create it with: python -m venv .venv && source .venv/bin/activate && pip install -e '.[server,tigergraph,llm,dev]'"
    exit 1
fi

# 2. Check .env file
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo -e "${YELLOW}[!] No .env file found. Creating from .env.example...${RESET}"
        cp .env.example .env
        echo -e "${YELLOW}[!] Please configure .env with your TIGERGRAPH_HOST and GOOGLE_API_KEY if using live services.${RESET}"
    fi
fi

# 3. Check frontend dependencies
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}[+] Installing frontend dependencies (npm install)...${RESET}"
    (cd frontend && npm install)
fi

# Configuration
BACKEND_PORT="${DEMO_PORT:-8000}"
BACKEND_HOST="${DEMO_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

# Process tracking
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    echo -e "\n${YELLOW}[*] Shutting down services...${RESET}"
    if [ -n "$BACKEND_PID" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    if [ -n "$FRONTEND_PID" ]; then
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi
    wait "$BACKEND_PID" 2>/dev/null || true
    wait "$FRONTEND_PID" 2>/dev/null || true
    echo -e "${GREEN}[✓] All services stopped cleanly.${RESET}"
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# 4. Start FastAPI backend
echo -e "${BLUE}[+] Starting FastAPI demo server on http://${BACKEND_HOST}:${BACKEND_PORT} ...${RESET}"
.venv/bin/python -m mcp_server.server &
BACKEND_PID=$!

# 5. Start Next.js frontend
echo -e "${BLUE}[+] Starting Next.js frontend on http://localhost:${FRONTEND_PORT} ...${RESET}"
(cd frontend && npm run dev -- -p "$FRONTEND_PORT") &
FRONTEND_PID=$!

# 6. Wait for backend to be ready
echo -e "${CYAN}[*] Waiting for backend to become healthy...${RESET}"
ATTEMPTS=0
MAX_ATTEMPTS=30
while [ $ATTEMPTS -lt $MAX_ATTEMPTS ]; do
    if curl -s "http://${BACKEND_HOST}:${BACKEND_PORT}/health" > /dev/null 2>&1; then
        break
    fi
    sleep 1
    ATTEMPTS=$((ATTEMPTS + 1))
done

if [ $ATTEMPTS -eq $MAX_ATTEMPTS ]; then
    echo -e "${RED}[!] Backend health check timed out. Check logs above.${RESET}"
else
    echo -e "${GREEN}[✓] Backend is healthy and ready!${RESET}"
fi

# 7. Print status summary
echo -e "\n${BOLD}${GREEN}================================================================${RESET}"
echo -e "${BOLD}${GREEN}                     SERVICES RUNNING                           ${RESET}"
echo -e "${BOLD}${GREEN}================================================================${RESET}"
echo -e "  ${BOLD}🖥️  Next.js Dashboard:${RESET}    ${CYAN}http://localhost:${FRONTEND_PORT}${RESET}"
echo -e "  ${BOLD}📊 Benchmarks & Pitch:${RESET}   ${CYAN}http://localhost:${FRONTEND_PORT}/benchmark${RESET}"
echo -e "  ${BOLD}📥 Ingest & Live Stream:${RESET} ${CYAN}http://localhost:${FRONTEND_PORT}/ingest${RESET}"
echo -e "  ${BOLD}📜 Protocol Inspector:${RESET}   ${CYAN}http://localhost:${FRONTEND_PORT}/protocol${RESET}"
echo -e "  ${BOLD}🔍 Query Lab:${RESET}            ${CYAN}http://localhost:${FRONTEND_PORT}/query${RESET}"
echo -e "  ${BOLD}⚡ Backend REST API:${RESET}     ${CYAN}http://${BACKEND_HOST}:${BACKEND_PORT}${RESET}"
echo -e "  ${BOLD}📖 Interactive Docs:${RESET}     ${CYAN}http://${BACKEND_HOST}:${BACKEND_PORT}/docs${RESET}"
echo -e "  ${BOLD}📡 SSE Event Feed:${RESET}       ${CYAN}http://${BACKEND_HOST}:${BACKEND_PORT}/stream/events${RESET}"
echo -e "\n  ${BOLD}🤖 MCP Client Stdio Config:${RESET}"
echo -e "     Command: ${BOLD}${SCRIPT_DIR}/.venv/bin/python${RESET}"
echo -e "     Args:    ${BOLD}[\"-m\", \"mcp_server.mcp_server\"]${RESET}"
echo -e "${BOLD}${GREEN}================================================================${RESET}"
echo -e "${YELLOW}Press Ctrl+C to stop all services.${RESET}\n"

# Keep script running while child processes are alive
wait
