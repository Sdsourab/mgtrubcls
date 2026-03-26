#!/usr/bin/env bash
set -e

echo ""
echo "  ╔═══════════════════════════════════════╗"
echo "  ║   UniSync — Rabindra University       ║"
echo "  ║   Department of Management            ║"
echo "  ╚═══════════════════════════════════════╝"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] python3 not found. Install Python 3.10+ first."
    exit 1
fi

# Create .env if missing
if [ ! -f ".env" ]; then
    echo "[WARNING] .env not found. Creating from template..."
    cp .env.example .env
    echo "[ACTION] Open .env and fill in your Supabase keys, then run this again."
    exit 1
fi

# Optional: create venv
if [ ! -d "venv" ]; then
    echo "[INFO] Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate 2>/dev/null || true

# Install dependencies
echo "[INFO] Installing dependencies..."
pip install -r requirements.txt --quiet

# Start
echo "[INFO] Starting UniSync → http://localhost:5000"
echo "[INFO] Press Ctrl+C to stop."
echo ""
python3 run.py
