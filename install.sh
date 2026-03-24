#!/bin/bash
set -euo pipefail

# ─── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ─── Banner ───────────────────────────────────────────────────────────────────
clear
echo -e "${CYAN}${BOLD}"
echo "  ╔══════════════════════════════════════════════════╗"
echo "  ║      AMNEZIA v2 — PREMIUM TERMINAL APP           ║"
echo "  ║      Powered by SkyKnight Network                ║"
echo "  ╚══════════════════════════════════════════════════╝"
echo -e "${NC}"

# ─── Step 1: Python3 ──────────────────────────────────────────────────────────
echo -e "${CYAN}[1/3]${NC} Checking Python3..."
if ! command -v python3 &>/dev/null; then
    echo -e "${YELLOW}  Python3 not found. Installing...${NC}"
    if command -v apt-get &>/dev/null; then
        sudo apt-get update -qq && sudo apt-get install -y -qq python3 python3-pip
    elif command -v yum &>/dev/null; then
        sudo yum install -y python3 python3-pip
    elif command -v brew &>/dev/null; then
        brew install python3
    else
        echo -e "${RED}  Error: cannot install Python3. Please install it manually.${NC}"
        exit 1
    fi
fi
PYTHON_VER=$(python3 --version 2>&1)
echo -e "  ${GREEN}✓${NC} ${PYTHON_VER}"

# ─── Step 2: Git ──────────────────────────────────────────────────────────────
echo -e "${CYAN}[2/3]${NC} Checking Git..."
if ! command -v git &>/dev/null; then
    echo -e "${YELLOW}  Git not found. Installing...${NC}"
    if command -v apt-get &>/dev/null; then
        sudo apt-get install -y -qq git
    elif command -v yum &>/dev/null; then
        sudo yum install -y git
    elif command -v brew &>/dev/null; then
        brew install git
    fi
fi
echo -e "  ${GREEN}✓${NC} Git ready"

# ─── Step 3: Clone & Launch ───────────────────────────────────────────────────
echo -e "${CYAN}[3/3]${NC} Downloading AmneziaWG Premium..."

REPO_URL="https://github.com/sky-night-net/amnezia-v2-deploy.git"
INSTALL_DIR="/tmp/amnezia-v2-setup"

# Always use a fresh copy
rm -rf "$INSTALL_DIR"
if ! git clone --depth=1 --quiet "$REPO_URL" "$INSTALL_DIR" 2>/dev/null; then
    echo -e "${RED}  Error: Failed to download repository.${NC}"
    echo -e "  Check your internet connection and try again."
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Downloaded"

# Change to script directory so relative paths (stats_hub/, etc.) work
cd "$INSTALL_DIR"

# ─── Launch ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}  Launching AmneziaWG Premium Terminal...${NC}"
echo ""

# Reconnect stdin to /dev/tty so interactive prompts work when piped through bash
exec python3 amnezia-cli.py </dev/tty
