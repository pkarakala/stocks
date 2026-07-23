#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Quant Console — Full Stack Launcher
# Runs the Python signal engine + React console in parallel
# ═══════════════════════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENGINE_DIR="$SCRIPT_DIR/engine"
CONSOLE_DIR="$SCRIPT_DIR/console"
DATA_DIR="$SCRIPT_DIR/data"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║              QUANT CONSOLE — Launcher                           ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# ─── Setup Python environment ─────────────────────────────────────────────────
if [ ! -d "$ENGINE_DIR/venv" ]; then
    echo "→ Creating Python virtual environment..."
    python3 -m venv "$ENGINE_DIR/venv"
    echo "→ Installing dependencies..."
    "$ENGINE_DIR/venv/bin/pip" install -q -r "$ENGINE_DIR/requirements.txt"
fi

# ─── Setup Node environment ───────────────────────────────────────────────────
if [ ! -d "$CONSOLE_DIR/node_modules" ]; then
    echo "→ Installing console dependencies..."
    cd "$CONSOLE_DIR" && npm install --silent
fi

# ─── Ensure data directory exists ─────────────────────────────────────────────
mkdir -p "$DATA_DIR"

# ─── Symlink data directory into console public (for dev server) ──────────────
if [ ! -L "$CONSOLE_DIR/public/data" ]; then
    ln -sf "$DATA_DIR" "$CONSOLE_DIR/public/data"
fi

echo ""
echo "→ Starting console (http://localhost:3000)..."
echo "  The console will show sample data until the pipeline runs."
echo ""
echo "  To generate live signals, run:"
echo "    cd engine && venv/bin/python pipeline.py"
echo ""

cd "$CONSOLE_DIR" && npm run dev
