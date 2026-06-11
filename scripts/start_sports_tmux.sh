#!/usr/bin/env bash
set -e

tmux has-session -t sports 2>/dev/null && {
  echo "Session sports already exists."
  exit 0
}

tmux new-session -d -s sports -n dashboard
tmux send-keys -t sports:dashboard 'cd ~/projects/papi-sports-intelligence && source .venv/bin/activate && streamlit run app/dashboard/main.py' C-m

tmux new-window -t sports -n testing
tmux send-keys -t sports:testing 'cd ~/projects/papi-sports-intelligence && source .venv/bin/activate' C-m

tmux new-window -t sports -n backtest
tmux send-keys -t sports:backtest 'cd ~/projects/papi-sports-intelligence && source .venv/bin/activate' C-m

tmux new-window -t sports -n dev
tmux send-keys -t sports:dev 'cd ~/projects/papi-sports-intelligence && source .venv/bin/activate' C-m

echo "Started tmux session: sports"
echo "Attach with: tmux a -t sports"
