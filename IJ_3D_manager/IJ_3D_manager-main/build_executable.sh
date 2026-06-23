#!/usr/bin/env bash
# ============================================================
#  IJ 3D Manager — Build Script (Linux)
#  Produces a single-file executable via PyInstaller.
#
#  Usage:
#    chmod +x build_executable.sh
#    ./build_executable.sh
#
#  Output: dist/IJ-3D-Manager  (standalone binary)
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo "  IJ 3D Manager — Build Pipeline"
echo "============================================"

# ── 1. Activate virtual environment ──────────────────────────
if [ -d "venv" ]; then
    echo "[1/4] Activating virtual environment..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "[1/4] Activating virtual environment (.venv)..."
    source .venv/bin/activate
else
    echo "[1/4] No virtual environment found — using system Python."
fi

# ── 2. Install PyInstaller ───────────────────────────────────
echo "[2/4] Installing/upgrading PyInstaller..."
pip install --quiet --upgrade pyinstaller

# ── 3. Locate CustomTkinter assets ───────────────────────────
echo "[3/4] Locating CustomTkinter package..."
CTK_PATH=$(python3 -c "import customtkinter; print(customtkinter.__path__[0])")
echo "       Found: $CTK_PATH"

# ── 4. Build ─────────────────────────────────────────────────
echo "[4/4] Building executable..."

pyinstaller \
    --noconfirm \
    --onefile \
    --windowed \
    --name "IJ-3D-Manager" \
    \
    --add-data "${CTK_PATH}:customtkinter" \
    --add-data "app_icon.png:." \
    \
    --hidden-import "PIL._tkinter_finder" \
    --hidden-import "customtkinter" \
    \
    --collect-submodules customtkinter \
    \
    app.py

echo ""
echo "============================================"
echo "  Build complete!"
echo "  Executable: dist/IJ-3D-Manager"
echo ""
echo "  To run:"
echo "    ./dist/IJ-3D-Manager"
echo ""
echo "  The database (print_manager_v2.db) and"
echo "  media folder (src_media/) will be created"
echo "  in the same directory as the executable."
echo "============================================"
