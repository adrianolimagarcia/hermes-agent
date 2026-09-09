#!/usr/bin/env bash
# ============================================================================
# HAOS (Hermes Agentic OS) — Universal Standalone Installer
# ============================================================================
# Installs HAOS from github.com/adrianolimagarcia/hermes-agent (branch haos-fork).
# Designed to coexist safely with or without an existing upstream Hermes installation.
# Sets up isolated virtual environment, dependencies, CLI binaries, and default configs.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/adrianolimagarcia/hermes-agent/haos-fork/scripts/install_haos.sh | bash
#
# Or with options:
#   ./scripts/install_haos.sh --branch haos-fork --haos-home ~/.haos
# ============================================================================

set -euo pipefail

# Visuals
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log_info()  { echo -e "${CYAN}ℹ${NC} $1"; }
log_ok()    { echo -e "${GREEN}✓${NC} $1"; }
log_warn()  { echo -e "${YELLOW}⚠${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }
log_step()  { echo -e "\n${BOLD}${BLUE}==>${NC} ${BOLD}$1${NC}"; }

# Defaults
REPO_URL="${HAOS_REPO_URL:-https://github.com/adrianolimagarcia/hermes-agent.git}"
BRANCH="${HAOS_BRANCH:-haos-standalone}"
HAOS_HOME="${HAOS_HOME:-$HOME/.haos}"

if [ "$(id -u)" -eq 0 ]; then
    DEFAULT_INSTALL_DIR="/usr/local/lib/haos-agent"
    BIN_DIR="/usr/local/bin"
else
    DEFAULT_INSTALL_DIR="$HOME/.local/share/haos-agent"
    BIN_DIR="$HOME/.local/bin"
fi

INSTALL_DIR="${HAOS_INSTALL_DIR:-$DEFAULT_INSTALL_DIR}"
SKIP_SYSTEM_DEPS=false
API_KEY="${A6_API_KEY:-}"

# Argument parsing
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dir) INSTALL_DIR="$2"; shift 2 ;;
        --branch) BRANCH="$2"; shift 2 ;;
        --haos-home) HAOS_HOME="$2"; shift 2 ;;
        --api-key) API_KEY="$2"; shift 2 ;;
        --skip-system-deps) SKIP_SYSTEM_DEPS=true; shift ;;
        --help|-h)
            echo "HAOS Standalone Installer"
            echo "Options:"
            echo "  --dir <path>          Target checkout directory (default: $DEFAULT_INSTALL_DIR)"
            echo "  --branch <name>       Git branch to clone (default: haos-fork)"
            echo "  --haos-home <path>    Configuration & data home directory (default: ~/.haos)"
            echo "  --api-key <key>       A6API Key to register in .env"
            echo "  --skip-system-deps    Skip apt/pacman/dnf package installation"
            exit 0
            ;;
        *) log_warn "Unknown argument: $1"; shift ;;
    esac
done

echo -e "${CYAN}"
echo "  ██╗  ██╗ █████╗  ██████╗ ███████╗"
echo "  ██║  ██║██╔══██╗██╔═══██╗██╔════╝"
echo "  ███████║███████║██║   ██║███████╗"
echo "  ██╔══██║██╔══██║██║   ██║╚════██║"
echo "  ██║  ██║██║  ██║╚██████╔╝███████║"
echo "  ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝"
echo "  Hermes Agentic Multi-Agent OS Installer"
echo -e "${NC}"

log_info "Target installation directory: ${BOLD}$INSTALL_DIR${NC}"
log_info "Configuration directory (HAOS_HOME): ${BOLD}$HAOS_HOME${NC}"
log_info "Git repository: ${BOLD}$REPO_URL ($BRANCH)${NC}"

# 1. System Package Detection
if [ "$SKIP_SYSTEM_DEPS" = false ]; then
    log_step "Checking and installing required system packages..."
    SUDO=""
    if [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
    fi

    if command -v pacman >/dev/null 2>&1; then
        log_info "Arch/CachyOS detected (pacman). Ensuring git, curl, socat, base-devel..."
        $SUDO pacman -S --needed --noconfirm git curl socat base-devel python >/dev/null 2>&1 || true
    elif command -v apt-get >/dev/null 2>&1; then
        log_info "Debian/Ubuntu detected (apt). Ensuring git, curl, socat, build-essential, python3-venv..."
        $SUDO apt-get update -qq >/dev/null 2>&1 || true
        $SUDO apt-get install -y -qq git curl socat build-essential python3-venv python3-pip >/dev/null 2>&1 || true
    elif command -v dnf >/dev/null 2>&1; then
        log_info "Fedora/RHEL detected (dnf). Ensuring git, curl, socat, gcc..."
        $SUDO dnf install -y git curl socat gcc make python3-devel >/dev/null 2>&1 || true
    elif command -v brew >/dev/null 2>&1; then
        log_info "macOS detected (brew). Ensuring git, curl, socat..."
        brew install git curl socat >/dev/null 2>&1 || true
    fi
fi

# 2. Check Git & Curl
command -v git >/dev/null 2>&1 || { log_error "git is required. Please install git."; exit 1; }
command -v curl >/dev/null 2>&1 || { log_error "curl is required. Please install curl."; exit 1; }

# 3. Clone or Update Repo
log_step "Fetching HAOS repository from GitHub..."
mkdir -p "$(dirname "$INSTALL_DIR")"
if [ -d "$INSTALL_DIR/.git" ]; then
    log_info "Updating existing checkout at $INSTALL_DIR..."
    cd "$INSTALL_DIR"
    git fetch origin "$BRANCH" || true
    git checkout "$BRANCH" || true
    git pull origin "$BRANCH" || true
else
    log_info "Cloning $REPO_URL ($BRANCH) into $INSTALL_DIR..."
    git clone --branch "$BRANCH" --single-branch "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# 4. Install UV for ultra-fast Python package management
log_step "Ensuring uv package manager..."
if ! command -v uv >/dev/null 2>&1; then
    log_info "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
fi

# 5. Create Isolated Virtual Environment
log_step "Configuring isolated virtual environment..."
VENV_DIR="$INSTALL_DIR/venv"
if command -v uv >/dev/null 2>&1; then
    uv venv "$VENV_DIR" --python 3.11 2>/dev/null || uv venv "$VENV_DIR"
    PYTHON="$VENV_DIR/bin/python"
    log_info "Installing HAOS package and dependencies via uv..."
    VIRTUAL_ENV="$VENV_DIR" uv pip install -e .
else
    log_warn "uv not found, falling back to python3 -m venv..."
    python3 -m venv "$VENV_DIR"
    PYTHON="$VENV_DIR/bin/python"
    "$PYTHON" -m pip install --upgrade pip
    "$PYTHON" -m pip install -e .
fi

# 6. Install Global CLI Wrappers
log_step "Installing global CLI wrappers..."
mkdir -p "$BIN_DIR"

cat << EOF > "$BIN_DIR/haos"
#!/usr/bin/env bash
export HAOS_HOME="\${HAOS_HOME:-$HAOS_HOME}"
export HERMES_HOME="\${HAOS_HOME}"
export HAOS_DATA_DIR="\${HAOS_DATA_DIR:-\$HAOS_HOME}"
unset PYTHONPATH
unset PYTHONHOME
if [ -x "$VENV_DIR/bin/haos" ]; then
    exec "$VENV_DIR/bin/haos" "\$@"
else
    export PYTHONPATH="$INSTALL_DIR:\${PYTHONPATH:-}"
    exec "$PYTHON" -m hermes_cli.main "\$@"
fi
EOF
chmod +x "$BIN_DIR/haos"

cat << EOF > "$BIN_DIR/haos-agent"
#!/usr/bin/env bash
export HAOS_HOME="\${HAOS_HOME:-$HAOS_HOME}"
export HERMES_HOME="\${HAOS_HOME}"
export HAOS_DATA_DIR="\${HAOS_DATA_DIR:-\$HAOS_HOME}"
unset PYTHONPATH
unset PYTHONHOME
export PYTHONPATH="$INSTALL_DIR:\${PYTHONPATH:-}"
cd "$INSTALL_DIR" 2>/dev/null || true
exec "$PYTHON" "$INSTALL_DIR/run_agent.py" "\$@"
EOF
chmod +x "$BIN_DIR/haos-agent"

cat << EOF > "$BIN_DIR/haos-controlplane"
#!/usr/bin/env bash
export HAOS_HOME="\${HAOS_HOME:-$HAOS_HOME}"
export HERMES_HOME="\${HAOS_HOME}"
export HAOS_DATA_DIR="\${HAOS_DATA_DIR:-\$HAOS_HOME}"
unset PYTHONPATH
unset PYTHONHOME
export PYTHONPATH="$INSTALL_DIR:\${PYTHONPATH:-}"
export PYTHON="$PYTHON"
export HERMES="$INSTALL_DIR/bin/haos"
exec bash "$INSTALL_DIR/scripts/serve_all.sh" "\$@"
EOF
chmod +x "$BIN_DIR/haos-controlplane"

cat << EOF > "$BIN_DIR/haos-motd"
#!/usr/bin/env bash
export HAOS_HOME="\${HAOS_HOME:-$HAOS_HOME}"
export HERMES_HOME="\${HAOS_HOME}"
exec "$PYTHON" "$INSTALL_DIR/scripts/haos_motd.py" "\$@"
EOF
chmod +x "$BIN_DIR/haos-motd"

log_ok "Installed wrappers: $BIN_DIR/haos, $BIN_DIR/haos-agent, $BIN_DIR/haos-controlplane, $BIN_DIR/haos-motd"

# 7. Initialize HAOS_HOME & Default Configs
log_step "Initializing configuration in $HAOS_HOME..."
mkdir -p "$HAOS_HOME"

if [ -n "$API_KEY" ]; then
    echo "A6_API_KEY=$API_KEY" > "$HAOS_HOME/.env"
    chmod 600 "$HAOS_HOME/.env"
    log_ok "Saved A6_API_KEY to $HAOS_HOME/.env"
elif [ ! -f "$HAOS_HOME/.env" ]; then
    touch "$HAOS_HOME/.env"
    chmod 600 "$HAOS_HOME/.env"
fi

if [ ! -f "$HAOS_HOME/config.yaml" ]; then
    cat << EOF > "$HAOS_HOME/config.yaml"
# HAOS Agentic Configuration
_config_version: 41
context_file_max_chars: 64000

skills:
  default_skills:
    - haos-control-plane
    - haos-lane-execution

model:
  default: deepseek-v4-flash
  provider: a6api

providers:
  a6api:
    base_url: "https://api.a6api.com/v1"
    key_env: "A6_API_KEY"
    api_mode: chat_completions
    models:
      - deepseek-v4-flash
      - gpt-5.6-luna

terminal:
  cwd: $INSTALL_DIR
  timeout: 180

display:
  skin: default
  show_reasoning: true
  reasoning_full: true
  background_process_notifications: verbose

security:
  redact_secrets: true

delegation:
  max_spawn_depth: 3
  role_models:
    mayor: deepseek-v4-flash
    witness: deepseek-v4
    polecat: deepseek-v4-flash
EOF
    log_ok "Created initial $HAOS_HOME/config.yaml"
fi

# 8. Verification
log_step "Verifying installation..."
INSTALLED_VER=$("$BIN_DIR/haos" --version 2>/dev/null || true)
if [ -n "$INSTALLED_VER" ]; then
    log_ok "HAOS successfully installed!"
    echo "  $INSTALLED_VER"
else
    log_warn "Installation completed, but '$BIN_DIR/haos --version' returned empty. Check PATH."
fi

echo ""
echo -e "${GREEN}============================================================================${NC}"
echo -e "${BOLD}${GREEN}🎉 HAOS (Hermes Agentic OS) is ready!${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo ""
echo "Quick Commands:"
echo "  • CLI Interface:            haos"
echo "  • Configuration & Status:   haos status"
echo "  • Run Agent directly:       haos-agent"
echo "  • Start Web Dashboards:     haos-controlplane"
echo ""
echo "Dashboards when running:"
echo "  👉 HAOS Control Plane (Team Graph & Terminal): http://localhost:8788/"
echo "============================================================================"
