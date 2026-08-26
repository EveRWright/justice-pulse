#!/bin/bash
# Rolling wire: harvest Texas court news, merge durable catalog, push Pages.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
WHEN="${1:-2d}"
python3 ingest/fetch_wire.py --when "$WHEN" --wayback-save 8
HUB="$HOME/Eve_Sovereign_Hub/Justice_Pulse/10_News_Wire_Archive"
mkdir -p "$HUB"
cp -a archive/captures.jsonl archive/README.md ingest/queries.txt "$HUB/"
cp entries.json "$HUB/entries_live_mirror.json"
git add archive/captures.jsonl entries.json
if git diff --staged --quiet; then
  echo "No catalog changes"
  exit 0
fi
git -c user.name="Justice Pulse wire" -c user.email="eve@texanoai.com" \
  commit -m "wire: refresh Texas court catalog $(date -u +%Y-%m-%dT%H:%MZ)"
git push origin main
echo "Pushed. Pages will rebuild."
