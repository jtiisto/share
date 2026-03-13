#!/bin/bash
# Quick share — create a note via the API from the command line
#
# Usage:
#   ./bin/share.sh "https://example.com"
#   ./bin/share.sh -t "My Title" "Some content here"
#   echo "piped text" | ./bin/share.sh
#   ./bin/share.sh -t "Title" < file.txt

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PORT=${SHARE_PORT:-9100}
API="http://localhost:$PORT/share/api"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

TITLE=""

# Parse flags
while getopts "t:p:" opt; do
    case $opt in
        t) TITLE="$OPTARG" ;;
        p) PORT="$OPTARG"; API="http://localhost:$PORT/share/api" ;;
        *) echo "Usage: $0 [-t title] [-p port] [content]"; exit 1 ;;
    esac
done
shift $((OPTIND - 1))

# Get content from args or stdin
if [ $# -gt 0 ]; then
    CONTENT="$*"
elif [ ! -t 0 ]; then
    CONTENT=$(cat)
else
    echo "Usage: $0 [-t title] [-p port] <content>"
    echo "       echo 'text' | $0 [-t title]"
    exit 1
fi

# Auto-derive title if not provided
if [ -z "$TITLE" ]; then
    # Check if content looks like a URL
    if echo "$CONTENT" | head -1 | grep -qE '^https?://'; then
        # Extract domain as title
        TITLE=$(echo "$CONTENT" | head -1 | sed -E 's|https?://([^/]+).*|\1|')
    else
        # Use first 50 chars of first line
        TITLE=$(echo "$CONTENT" | head -1 | cut -c1-50)
    fi
fi

# Escape for JSON
json_escape() {
    printf '%s' "$1" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()), end="")'
}

JSON_TITLE=$(json_escape "$TITLE")
JSON_CONTENT=$(json_escape "$CONTENT")

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API/items" \
    -H "Content-Type: application/json" \
    -d "{\"title\": $JSON_TITLE, \"content\": $JSON_CONTENT}" 2>&1)

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}Shared:${NC} $TITLE"
else
    echo -e "${RED}Failed (HTTP $HTTP_CODE):${NC} $BODY"
    exit 1
fi
