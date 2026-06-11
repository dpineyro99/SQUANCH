#!/usr/bin/env bash
set -e

tmux has-session -t polymarket 2>/dev/null && {
  echo "Session polymarket already exists."
  exit 0
}

tmux new-session -d -s polymarket -n tracker
tmux send-keys -t polymarket:tracker 'cd ~/polymarket_bot && source venv/bin/activate && python3 alpha_tracker.py' C-m

tmux new-window -t polymarket -n explorer
tmux send-keys -t polymarket:explorer 'cd ~/polymarket_bot && source venv/bin/activate && python3 exploration_alpha_bot.py --loop --sleep 60' C-m

tmux new-window -t polymarket -n paper
tmux send-keys -t polymarket:paper 'cd ~/polymarket_bot && source venv/bin/activate' C-m

tmux new-window -t polymarket -n dev
tmux send-keys -t polymarket:dev 'cd ~/polymarket_bot && source venv/bin/activate' C-m

echo "Started tmux session: polymarket"
echo "Attach with: tmux a -t polymarket"
