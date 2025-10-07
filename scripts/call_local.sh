
#!/usr/bin/env bash
set -euo pipefail
URL=${1:-http://localhost:8000/transcribe}
curl -s -X POST "$URL" -F "file=@samples/hello.m4a" | jq .
