#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  AmneziaWG v2 Premium — INSTALLER / UPDATER
#  github.com/sky-night-net/amnezia-v2-deploy
#
#  First install:  curl -sL https://raw.githubusercontent.com/sky-night-net/amnezia-v2-deploy/main/install.sh | bash
#  Run later:      amnezia          (or ~/.amnezia-v2/run.sh)
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

# ─── Colors ──────────────────────────────────────────────────────────────────
R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'
C='\033[0;36m'; B='\033[1m'; N='\033[0m'

REPO_URL="https://github.com/sky-night-net/amnezia-v2-deploy.git"
INSTALL_DIR="$HOME/.amnezia-v2"
BIN_LINK="/usr/local/bin/amnezia"

clear
echo -e "${C}${B}"
echo "  ╔══════════════════════════════════════════════════╗"
echo "  ║      AMNEZIA v2 — PREMIUM INSTALLER             ║"
echo "  ║      Powered by SkyKnight Network               ║"
echo "  ╚══════════════════════════════════════════════════╝"
echo -e "${N}"

# ─── Detect OS & package manager ─────────────────────────────────────────────
PKG_MANAGER=""
if   command -v apt-get &>/dev/null; then PKG_MANAGER="apt"
elif command -v yum     &>/dev/null; then PKG_MANAGER="yum"
elif command -v dnf     &>/dev/null; then PKG_MANAGER="dnf"
elif command -v brew    &>/dev/null; then PKG_MANAGER="brew"
fi

install_pkg() {
  case "$PKG_MANAGER" in
    apt)  sudo apt-get install -y -qq "$@" ;;
    yum)  sudo yum install -y "$@" ;;
    dnf)  sudo dnf install -y "$@" ;;
    brew) brew install "$@" ;;
    *)    echo -e "${R}  Cannot install $*. Please install manually.${N}"; exit 1 ;;
  esac
}

# ─── Step 1: Python3 ──────────────────────────────────────────────────────────
echo -e "${C}[1/4]${N} Checking Python 3..."
if ! command -v python3 &>/dev/null; then
  echo -e "  ${Y}Installing Python 3...${N}"
  [ "$PKG_MANAGER" = "apt" ] && sudo apt-get update -qq
  install_pkg python3 python3-pip
fi
echo -e "  ${G}✓${N} $(python3 --version)"

# ─── Step 2: Git ─────────────────────────────────────────────────────────────
echo -e "${C}[2/4]${N} Checking Git..."
if ! command -v git &>/dev/null; then
  echo -e "  ${Y}Installing Git...${N}"
  install_pkg git
fi
echo -e "  ${G}✓${N} Git ready"

# ─── Step 3: Clone or update ──────────────────────────────────────────────────
echo -e "${C}[3/4]${N} Installing to ${B}${INSTALL_DIR}${N}..."

if [ -d "$INSTALL_DIR/.git" ]; then
  # Already installed — just update
  echo -e "  ${Y}Already installed. Pulling latest updates...${N}"
  git -C "$INSTALL_DIR" pull --ff-only --quiet
  LOCAL_VER=$(cat "$INSTALL_DIR/VERSION" 2>/dev/null || echo "?")
  echo -e "  ${G}✓${N} Updated to v${LOCAL_VER}"
else
  # Fresh install
  echo -e "  Cloning repository..."
  git clone --depth=1 --quiet "$REPO_URL" "$INSTALL_DIR"
  LOCAL_VER=$(cat "$INSTALL_DIR/VERSION" 2>/dev/null || echo "?")
  echo -e "  ${G}✓${N} Installed v${LOCAL_VER}"
fi

# ─── Step 4: Create global launcher ──────────────────────────────────────────
echo -e "${C}[4/4]${N} Creating launcher command ${B}amnezia${N}..."

# Write run.sh inside install dir
cat > "$INSTALL_DIR/run.sh" << 'RUNSCRIPT'
#!/bin/bash
cd "$(dirname "$0")"
exec python3 amnezia-cli.py </dev/tty
RUNSCRIPT
chmod +x "$INSTALL_DIR/run.sh"

# Create symlink /usr/local/bin/amnezia → run.sh (try with sudo if needed)
if [ -d "/usr/local/bin" ]; then
  if ln -sf "$INSTALL_DIR/run.sh" "$BIN_LINK" 2>/dev/null; then
    echo -e "  ${G}✓${N} Command ${B}amnezia${N} is now available globally"
  elif sudo ln -sf "$INSTALL_DIR/run.sh" "$BIN_LINK" 2>/dev/null; then
    echo -e "  ${G}✓${N} Command ${B}amnezia${N} is now available globally (sudo)"
  else
    echo -e "  ${Y}⚠${N}  Could not create global command. Run manually:"
    echo -e "     bash ${INSTALL_DIR}/run.sh"
  fi
fi

# ─── Done ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${G}${B}  ✅  Installation complete!${N}"
echo ""
echo -e "  ${B}To run AmneziaWG:${N}"
echo -e "     ${G}amnezia${N}                  (if command is available)"
echo -e "     ${G}bash ~/.amnezia-v2/run.sh${N} (always works)"
echo ""

# Auto-launch after fresh install (but not when piped)
if [ -t 0 ]; then
  exec "$INSTALL_DIR/run.sh"
else
  # Piped mode (curl | bash) — reconnect tty and launch
  exec python3 "$INSTALL_DIR/amnezia-cli.py" </dev/tty
fi
