#!/usr/bin/env bash
set -e

PANE_ID="$1"
TAB_ID="$2"
SESSION_ID="$3"
AGENT_ID="$4"
CARRYOVER_PATH="$5"

if [[ -z "$PANE_ID" || -z "$TAB_ID" || -z "$SESSION_ID" || -z "$AGENT_ID" ]]; then
  echo "Usage: $0 <pane_id> <tab_id> <session_id> <agent_id> [carryover_path]"
  exit 1
fi

if [[ ! "$PANE_ID" =~ ^[a-zA-Z0-9_:-]+$ ]]; then echo "Invalid PANE_ID" && exit 1; fi
if [[ ! "$TAB_ID" =~ ^[a-zA-Z0-9_:-]+$ ]]; then echo "Invalid TAB_ID" && exit 1; fi
if [[ ! "$SESSION_ID" =~ ^[a-zA-Z0-9_:-]+$ ]]; then echo "Invalid SESSION_ID" && exit 1; fi
if [[ ! "$AGENT_ID" =~ ^[a-zA-Z0-9_:-]+$ ]]; then echo "Invalid AGENT_ID" && exit 1; fi

HANDOFF_DIR=".pi/handoff/$SESSION_ID/$AGENT_ID"
mkdir -p "$HANDOFF_DIR"
touch "$HANDOFF_DIR/journal.json" "$HANDOFF_DIR/dispatch.json"

TIMESTAMP=$(date -u +"%Y%m%d-%H%M%S")

# Write sealed state with pane metadata
echo "{\"status\": \"sealed\", \"timestamp\": \"$TIMESTAMP\", \"pane_id\": \"$PANE_ID\", \"tab_id\": \"$TAB_ID\", \"carryover_path\": \"$CARRYOVER_PATH\"}" > "$HANDOFF_DIR/dispatch.json"

HERDR_BIN="herdr"
if ! command -v herdr >/dev/null 2>&1; then
  HERDR_BIN="$HOME/.local/share/mise/installs/herdr/0.8.0/herdr"
fi

"$HERDR_BIN" tab rename "$TAB_ID" "${AGENT_ID}-sealed" >> "$HANDOFF_DIR/rotate.log" 2>&1 || true
