#!/bin/sh
# ---------------------------------------------------------
# AegisArchive 1-Click Launcher for Linux
# ---------------------------------------------------------
cd "$(dirname "$0")" || exit 1

echo "=========================================================="
echo "  Starting AegisArchive Web Console (Linux)..."
echo "=========================================================="

if command -v python3 >/dev/null 2>&1; then
    exec python3 cli/launch.py
elif command -v python >/dev/null 2>&1; then
    exec python cli/launch.py
else
    echo "[Error] Python 3 was not found."
    printf "%s" "Press Enter to exit..."
    read -r reply
fi
