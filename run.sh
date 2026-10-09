#!/usr/bin/env bash
#
# Image Agent - Unified Local Image Generation Interface
# Apple Silicon (M5) + Draw Things + Bonsai 2
#

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "=================================================="
echo "✨ Starting Image Agent..."
echo "=================================================="

# 1. Environment & Dependencies
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment (.venv)..."
    uv venv .venv
    echo "📦 Installing requirements..."
    uv pip install --python .venv -r requirements.txt
fi

PYTHON="$DIR/.venv/bin/python"

# 2. Check Services
echo "🔍 Checking local services..."

# Check Draw Things
if curl -s --max-time 1.5 "http://127.0.0.1:7860/sdapi/v1/options" > /dev/null 2>&1; then
    echo "  ✅ Draw Things API: Online (http://127.0.0.1:7860)"
else
    echo "  ⚠️  Draw Things API: Offline"
    echo "     Пожалуйста, запусти Draw Things и включи API Server (HTTP :7860)"
fi

# Check Bonsai 2
BONSAI_URL="${BONSAI_BASE_URL:-http://127.0.0.1:8080/v1}"
if curl -s --max-time 1.5 "${BONSAI_URL}/models" > /dev/null 2>&1 || curl -s --max-time 1.5 "http://127.0.0.1:8080/health" > /dev/null 2>&1; then
    echo "  ✅ Bonsai 2 LLM: Online ($BONSAI_URL)"
else
    echo "  ℹ️  Bonsai 2: Offline -> Image Agent запустится в режиме Simple Mode"
    echo "     (Для запуска Bonsai: cd ../Bonsai-demo && ./scripts/start_llama_server.sh)"
fi

PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"

echo ""
echo "🚀 Web UI доступен по адресу: http://$HOST:$PORT"
echo "=================================================="
echo ""

# Open browser in background after 1s
(sleep 1.2 && open "http://$HOST:$PORT") > /dev/null 2>&1 &

# Run server
exec "$PYTHON" -m uvicorn app.main:app --host "$HOST" --port "$PORT"
