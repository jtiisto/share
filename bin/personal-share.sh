#!/bin/bash
# Quick share — create a note or upload a file via the API from the command line
#
# Usage:
#   ./bin/share.sh "https://example.com"
#   ./bin/share.sh -t "My Title" "Some content here"
#   ./bin/share.sh -c "recipes" "Grandma's cookie recipe..."
#   ./bin/share.sh /path/to/file.pdf
#   ./bin/share.sh -c "docs" -t "Manual" /path/to/file.pdf
#   echo "piped text" | ./bin/share.sh
#   echo "piped text" | ./bin/share.sh -c "links"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PORT=${SHARE_PORT:-9100}
API="http://localhost:$PORT/share/api"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

TITLE=""
CATEGORY=""

# Parse flags
while getopts "t:c:p:" opt; do
    case $opt in
        t) TITLE="$OPTARG" ;;
        c) CATEGORY="$OPTARG" ;;
        p) PORT="$OPTARG"; API="http://localhost:$PORT/share/api" ;;
        *) echo "Usage: $0 [-t title] [-c category] [-p port] <content or file path>"
           echo "       echo 'text' | $0 [-t title] [-c category]"
           exit 1 ;;
    esac
done
shift $((OPTIND - 1))

# Determine input mode: file, args, or pipe
FILE_PATH=""
CONTENT=""
FROM_PIPE=false

DIR_PATH=""

if [ $# -gt 0 ]; then
    # Check if the argument is an existing directory
    if [ $# -eq 1 ] && [ -d "$1" ]; then
        DIR_PATH="$(cd "$1" && pwd)"
    # Check if the argument is an existing file
    elif [ $# -eq 1 ] && [ -f "$1" ]; then
        FILE_PATH="$1"
    else
        CONTENT="$*"
    fi
elif [ ! -t 0 ]; then
    CONTENT=$(cat)
    FROM_PIPE=true
else
    echo "Usage: $0 [-t title] [-c category] [-p port] <content or file path>"
    echo "       echo 'text' | $0 [-t title] [-c category]"
    exit 1
fi

# Escape for JSON
json_escape() {
    printf '%s' "$1" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()), end="")'
}

# --- Directory sharing ---
if [ -n "$DIR_PATH" ]; then
    JSON_PATH=$(json_escape "$DIR_PATH")

    RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API/folders" \
        -H "Content-Type: application/json" \
        -d "{\"target_path\": $JSON_PATH}" 2>&1)

    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    BODY=$(echo "$RESPONSE" | head -n -1)

    if [ "$HTTP_CODE" = "200" ]; then
        NAME=$(echo "$BODY" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())["name"])')
        echo -e "${GREEN}Shared folder:${NC} $DIR_PATH (as $NAME)"
    else
        echo -e "${RED}Failed (HTTP $HTTP_CODE):${NC} $BODY"
        exit 1
    fi
    exit 0
fi

# --- File upload ---
if [ -n "$FILE_PATH" ]; then
    FILENAME=$(basename "$FILE_PATH")
    DISPLAY_TITLE="${TITLE:-$FILENAME}"

    CURL_ARGS=(-s -w "\n%{http_code}" -X POST "$API/items/upload"
        -F "file=@$FILE_PATH"
        -F "category=$CATEGORY"
        -F "title=${TITLE}")

    RESPONSE=$(curl "${CURL_ARGS[@]}" 2>&1)
    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    BODY=$(echo "$RESPONSE" | head -n -1)

    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}Uploaded:${NC} $DISPLAY_TITLE"
    else
        echo -e "${RED}Failed (HTTP $HTTP_CODE):${NC} $BODY"
        exit 1
    fi
    exit 0
fi

# --- Note creation ---

# Auto-derive title if not provided
if [ -z "$TITLE" ]; then
    if echo "$CONTENT" | head -1 | grep -qE '^https?://'; then
        TITLE=$(echo "$CONTENT" | head -1 | sed -E 's|https?://([^/]+).*|\1|')
    else
        TITLE=$(echo "$CONTENT" | head -1 | cut -c1-50)
    fi
fi

JSON_TITLE=$(json_escape "$TITLE")
JSON_CONTENT=$(json_escape "$CONTENT")
JSON_CATEGORY=$(json_escape "$CATEGORY")

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API/items" \
    -H "Content-Type: application/json" \
    -d "{\"title\": $JSON_TITLE, \"content\": $JSON_CONTENT, \"category\": $JSON_CATEGORY}" 2>&1)

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}Shared:${NC} $TITLE"
else
    echo -e "${RED}Failed (HTTP $HTTP_CODE):${NC} $BODY"
    exit 1
fi
