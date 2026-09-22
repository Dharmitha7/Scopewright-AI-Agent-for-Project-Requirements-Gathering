#!/usr/bin/env bash
# Smoke test for D70/D71: sign in, create a project, upload a real .md file
# (Docling-routed, no fallback), poll until it's done, and print the
# resulting evidence chunk + its embedding dimension straight from Postgres.
#
# Run from anywhere with the stack up (docker compose up -d):
#   bash scripts/smoke_test_ingestion.sh
set -euo pipefail

BASE="http://localhost:8000"
COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT

echo "== sign in =="
curl -sf -c "$COOKIE_JAR" -X POST "$BASE/auth/dev-session" \
  -H "Content-Type: application/json" \
  -d '{"display_name":"Smoke Test","email":"smoketest@example.com"}' \
  -o /dev/null
echo "ok"

echo "== create project =="
PROJECT_JSON=$(curl -sf -b "$COOKIE_JAR" -X POST "$BASE/projects" \
  -H "Content-Type: application/json" \
  -d '{"brief":"A tool to test Docling and EmbeddingGemma end to end"}')
PROJECT_ID=$(echo "$PROJECT_JSON" | grep -oE '"id":"[^"]+"' | head -1 | cut -d'"' -f4)
echo "project_id=$PROJECT_ID"

echo "== upload a Docling-routed .md file =="
TMP_MD="$(mktemp --suffix=.md)"
cat > "$TMP_MD" <<'EOF'
# Vendor Notes

The vendor API rate limit is 120 requests per minute.

## Table 1
| Name | Role |
|------|------|
| Priya | Product owner |
EOF

UPLOAD_JSON=$(curl -sf -b "$COOKIE_JAR" -X POST "$BASE/projects/$PROJECT_ID/uploads" \
  -F "file=@${TMP_MD};type=text/markdown;filename=smoke.md")
UPLOAD_ID=$(echo "$UPLOAD_JSON" | grep -oE '"id":"[^"]+"' | head -1 | cut -d'"' -f4)
echo "upload_id=$UPLOAD_ID"
rm -f "$TMP_MD"

echo "== poll upload status (job worker runs every ~2s) =="
for _ in $(seq 1 30); do
  STATUS=$(curl -sf -b "$COOKIE_JAR" "$BASE/projects/$PROJECT_ID/uploads" \
    | grep -oE "\"id\":\"$UPLOAD_ID\"[^}]*\"status\":\"[a-z]+\"" \
    | grep -oE '"status":"[a-z]+"' | cut -d'"' -f4)
  echo "  status=$STATUS"
  [ "$STATUS" = "done" ] && break
  [ "$STATUS" = "failed" ] && { echo "INGEST FAILED"; exit 1; }
  sleep 2
done

echo "== evidence chunks + embedding width, straight from Postgres =="
docker compose exec -T postgres psql -U crewlane -d crewlane -c \
  "SELECT chunk_index, left(body, 60) AS body_preview, vector_dims(embedding) AS dims
   FROM evidence_chunks
   WHERE upload_id = '$UPLOAD_ID'
   ORDER BY chunk_index;"

echo "== ask the chat something only this upload can answer =="
ASK_JSON=$(curl -sf -b "$COOKIE_JAR" -X POST "$BASE/projects/$PROJECT_ID/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"what did the notes say about the vendor API rate limit?"}')
echo "$ASK_JSON" | python3 -c "import sys,json; [print('-', m.get('content','')[:300]) for m in json.load(sys.stdin) if m.get('role')=='assistant']" 2>/dev/null || echo "$ASK_JSON"
