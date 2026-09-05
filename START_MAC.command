#!/bin/bash
# ---------------------------------------------------------
# AegisArchive 1-Click Launcher for macOS
# ---------------------------------------------------------
cd "$(dirname "$0")" || exit 1

echo "=========================================================="
echo "  Starting AegisArchive Web Console (macOS)..."
echo "=========================================================="

if command -v python3 >/dev/null 2>&1; then
    exec python3 cli/launch.py
elif command -v python >/dev/null 2>&1; then
    exec python cli/launch.py
else
    echo "[Error] Python 3 was not found on this Mac."
    echo "Please install Python 3 from https://python.org or Homebrew."
    read -p "Press Enter to exit..."
fi
