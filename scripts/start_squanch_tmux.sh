#!/usr/bin/env bash
set -e

tmux has-session -t squanch 2>/dev/null && {
  echo "Session squanch already exists."
  exit 0
}

tmux new-session -d -s squanch -n dashboard
tmux send-keys -t squanch:dashboard 'cd ~/jarvis/dashboard && npm run dev' C-m

tmux new-window -t squanch -n backend
tmux send-keys -t squanch:backend 'cd ~/jarvis/backend && source .venv/bin/activate && uvicorn main:app --reload --host 0.0.0.0 --port 8000' C-m

tmux new-window -t squanch -n telegram
tmux send-keys -t squanch:telegram 'cd ~/jarvis/backend && source .venv/bin/activate && python telegram_bot.py' C-m

tmux new-window -t squanch -n executor
tmux send-keys -t squanch:executor 'cd ~/jarvis/backend && source .venv/bin/activate && python3 executor_agent.py' C-m

tmux new-window -t squanch -n reminder
tmux send-keys -t squanch:reminder 'cd ~/jarvis/backend && source .venv/bin/activate && python reminder_worker.py' C-m

tmux new-window -t squanch -n dev
tmux send-keys -t squanch:dev 'cd ~/jarvis' C-m

echo "Started tmux session: squanch"
echo "Attach with: tmux a -t squanch"
