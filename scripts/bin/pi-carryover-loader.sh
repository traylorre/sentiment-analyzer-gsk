#!/usr/bin/env bash
set -e

PANE_ID="$1"
TAB_ID="$2"
SESSION_ID="$3"
AGENT_ID="$4"

if [[ -z "$PANE_ID" || -z "$TAB_ID" || -z "$SESSION_ID" || -z "$AGENT_ID" ]]; then
  echo "Usage: $0 <pane_id> <tab_id> <session_id> <agent_id>"
  exit 1
fi

if [[ ! "$PANE_ID" =~ ^[a-zA-Z0-9_:-]+$ ]]; then echo "Invalid PANE_ID" && exit 1; fi
if [[ ! "$TAB_ID" =~ ^[a-zA-Z0-9_:-]+$ ]]; then echo "Invalid TAB_ID" && exit 1; fi
if [[ ! "$SESSION_ID" =~ ^[a-zA-Z0-9_:-]+$ ]]; then echo "Invalid SESSION_ID" && exit 1; fi
if [[ ! "$AGENT_ID" =~ ^[a-zA-Z0-9_:-]+$ ]]; then echo "Invalid AGENT_ID" && exit 1; fi

HANDOFF_DIR=".pi/handoff/$SESSION_ID/$AGENT_ID"
mkdir -p "$HANDOFF_DIR"
touch "$HANDOFF_DIR/journal.json" "$HANDOFF_DIR/dispatch.json"

HERDR_BIN="herdr"
if ! command -v herdr >/dev/null 2>&1; then
  HERDR_BIN="$HOME/.local/share/mise/installs/herdr/0.8.0/herdr"
fi

"$HERDR_BIN" tab rename "$TAB_ID" "$AGENT_ID" >> "$HANDOFF_DIR/rotate.log" 2>&1 || true
