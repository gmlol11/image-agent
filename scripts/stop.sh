#!/usr/bin/env bash
# Stop Image Agent and Bonsai 2 services cleanly

# 1. Stop Image Agent (port 8000)
AGENT_PIDS=$(lsof -ti :8000 2>/dev/null || true)
if [ -n "$AGENT_PIDS" ]; then
    kill $AGENT_PIDS 2>/dev/null || true
    sleep 0.5
    kill -9 $AGENT_PIDS 2>/dev/null || true
fi

# 2. Stop Bonsai 2 llama-server (port 8080)
BONSAI_PIDS=$(lsof -ti :8080 2>/dev/null || true)
if [ -n "$BONSAI_PIDS" ]; then
    kill $BONSAI_PIDS 2>/dev/null || true
    sleep 0.5
    kill -9 $BONSAI_PIDS 2>/dev/null || true
fi

# Also check any stray uvicorn or llama-server under image-agent / Bonsai-demo
pkill -f "uvicorn app.main:app" 2>/dev/null || true

# 3. Send notification
osascript -e 'display notification "Image Agent и Bonsai 2 остановлены. Память освобождена." with title "Image Agent выключен" sound name "Blow"' >/dev/null 2>&1 || true
