#!/usr/bin/env bash
# Start Image Agent and supporting services in background
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BONSAI_DIR="$(cd "$DIR/../Bonsai-demo" 2>/dev/null && pwd || echo "")"
LOGS_DIR="$DIR/logs"
mkdir -p "$LOGS_DIR"

# 1. Check Draw Things
if ! pgrep -x "DrawThings" > /dev/null 2>&1 && ! pgrep -afil "Draw Things" > /dev/null 2>&1; then
    if [ -d "/Applications/Draw Things.app" ]; then
        open -a "/Applications/Draw Things.app"
    fi
fi

# 2. Check and start Bonsai 2 (port 8080)
if ! curl -s --max-time 1 "http://127.0.0.1:8080/health" > /dev/null 2>&1; then
    if [ -n "$BONSAI_DIR" ] && [ -f "$BONSAI_DIR/scripts/start_llama_server.sh" ]; then
        (
            cd "$BONSAI_DIR"
            PORT=8080 nohup ./scripts/start_llama_server.sh > "$LOGS_DIR/bonsai.log" 2>&1 &
        )
    fi
fi

# 3. Check and start Image Agent (port 8000)
if ! curl -s --max-time 1 "http://127.0.0.1:8000/api/health" > /dev/null 2>&1; then
    (
        cd "$DIR"
        nohup "$DIR/.venv/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > "$LOGS_DIR/image_agent.log" 2>&1 &
    )
fi

# 4. Wait for Image Agent to become ready
READY=0
for i in {1..25}; do
    if curl -s --max-time 1 "http://127.0.0.1:8000/api/health" > /dev/null 2>&1; then
        READY=1
        break
    fi
    sleep 0.8
done

# 5. Open browser & send notification
open "http://127.0.0.1:8000"

if [ "$READY" -eq 1 ]; then
    osascript -e 'display notification "Интерфейс открыт в браузере (http://127.0.0.1:8000)" with title "Image Agent запущен" sound name "Glass"' >/dev/null 2>&1 || true
else
    osascript -e 'display notification "Сервер запускается, вкладка в браузере открыта." with title "Image Agent запускается..."' >/dev/null 2>&1 || true
fi
