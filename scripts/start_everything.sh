#!/usr/bin/env bash
set -e

echo "Starting SQUANCH..."
~/scripts/start_squanch_tmux.sh || true

echo "Starting Sports Intelligence..."
~/scripts/start_sports_tmux.sh || true

echo "Starting Polymarket Alpha..."
~/scripts/start_polymarket_tmux.sh || true

echo ""
echo "All sessions requested."
echo ""
tmux ls
echo ""
echo "Attach commands:"
echo "  tmux a -t squanch"
echo "  tmux a -t sports"
echo "  tmux a -t polymarket"
