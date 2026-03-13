#!/bin/bash
# Fetch items from Personal Share — download files or export notes as Markdown
#
# Usage:
#   personal-fetch.sh --list                        # list recent items
#   personal-fetch.sh --list --type note             # list notes only
#   personal-fetch.sh --list --category "docs"       # list items in category
#   personal-fetch.sh "search term"                  # fetch by partial title match
#   personal-fetch.sh -o /tmp "search term"          # fetch to specific directory

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PORT=${SHARE_PORT:-9100}
API="http://localhost:$PORT/share/api"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
DIM='\033[2m'
NC='\033[0m'

OUTPUT_DIR="."
LIST_MODE=false
TYPE_FILTER=""
CATEGORY_FILTER=""

# Parse flags
while [[ $# -gt 0 ]]; do
    case $1 in
        --list) LIST_MODE=true; shift ;;
        --type) TYPE_FILTER="$2"; shift 2 ;;
        --category) CATEGORY_FILTER="$2"; shift 2 ;;
        -o) OUTPUT_DIR="$2"; shift 2 ;;
        -p) PORT="$2"; API="http://localhost:$PORT/share/api"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [options] [search term]"
            echo ""
            echo "Options:"
            echo "  --list                 List recent items"
            echo "  --type note|file       Filter by type (with --list)"
            echo "  --category \"name\"      Filter by category (with --list)"
            echo "  -o /path/to/dir        Output directory (default: current dir)"
            echo "  -p port                Server port (default: 9100)"
            echo ""
            echo "Examples:"
            echo "  $0 --list"
            echo "  $0 --list --type file"
            echo "  $0 \"report\""
            echo "  $0 -o /tmp \"cookie recipe\""
            exit 0
            ;;
        *) break ;;
    esac
done

SEARCH_TERM="$*"

# Fetch items from API
fetch_items() {
    local url="$API/items?"
    if [ -n "$TYPE_FILTER" ]; then
        url="${url}type=${TYPE_FILTER}&"
    fi
    if [ -n "$CATEGORY_FILTER" ]; then
        url="${url}category=${CATEGORY_FILTER}&"
    fi
    curl -s "$url" 2>/dev/null
}

# Format relative time
format_time() {
    local iso="$1"
    if [ -z "$iso" ]; then echo ""; return; fi
    local ts=$(date -d "$iso" +%s 2>/dev/null || date -j -f "%Y-%m-%dT%H:%M:%S" "${iso%%.*}" +%s 2>/dev/null)
    local now=$(date +%s)
    local diff=$((now - ts))
    if [ $diff -lt 60 ]; then echo "just now"
    elif [ $diff -lt 3600 ]; then echo "$((diff / 60))m ago"
    elif [ $diff -lt 86400 ]; then echo "$((diff / 3600))h ago"
    elif [ $diff -lt 604800 ]; then echo "$((diff / 86400))d ago"
    else date -d "$iso" +%Y-%m-%d 2>/dev/null || echo "$iso"; fi
}

# Safe filename from title
safe_filename() {
    printf '%s' "$1" | tr '/:*?"<>|\\' '_' | tr -s '_' | sed 's/^_//;s/_$//'
}

# Add number suffix if file exists
unique_path() {
    local dir="$1" name="$2" ext="$3"
    local path="$dir/$name$ext"
    if [ ! -e "$path" ]; then echo "$path"; return; fi
    local i=1
    while [ -e "$dir/${name}_${i}${ext}" ]; do i=$((i + 1)); done
    echo "$dir/${name}_${i}${ext}"
}

# --- List mode ---
if $LIST_MODE; then
    ITEMS=$(fetch_items)
    if [ -z "$ITEMS" ] || [ "$ITEMS" = "[]" ]; then
        echo "No items found."
        exit 0
    fi

    echo "$ITEMS" | python3 -c "
import sys, json
items = json.load(sys.stdin)
for item in items:
    typ = item.get('type', '?')
    title = item.get('title', '(untitled)')[:50]
    cat = item.get('category', '')
    cat_str = f'({cat})' if cat else ''
    pinned = '*' if item.get('pinned') else ' '
    print(f'{pinned} [{typ:4s}]  {title:<50s} {cat_str:<15s}')
"
    exit 0
fi

# --- Fetch mode ---
if [ -z "$SEARCH_TERM" ]; then
    echo "Usage: $0 [--list] [search term]"
    echo "Run with --help for full usage."
    exit 1
fi

# Search for matching items
ITEMS=$(fetch_items)
if [ -z "$ITEMS" ] || [ "$ITEMS" = "[]" ]; then
    echo -e "${RED}Error: No items found on server${NC}"
    exit 1
fi

MATCHES=$(echo "$ITEMS" | python3 -c "
import sys, json
items = json.load(sys.stdin)
term = '''$SEARCH_TERM'''.lower()
matches = [i for i in items if term in i.get('title', '').lower()]
print(json.dumps(matches))
")

MATCH_COUNT=$(echo "$MATCHES" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")

if [ "$MATCH_COUNT" -eq 0 ]; then
    echo -e "${RED}Error: No items matching \"$SEARCH_TERM\"${NC}"
    exit 1
fi

if [ "$MATCH_COUNT" -gt 1 ]; then
    echo -e "${YELLOW}Ambiguous: $MATCH_COUNT items match \"$SEARCH_TERM\":${NC}"
    echo "$MATCHES" | python3 -c "
import sys, json
items = json.load(sys.stdin)
for item in items:
    typ = item.get('type', '?')
    title = item.get('title', '(untitled)')
    cat = item.get('category', '')
    cat_str = f' ({cat})' if cat else ''
    print(f'  [{typ}] {title}{cat_str}')
"
    echo ""
    echo "Refine your search to match exactly one item."
    exit 1
fi

# Exactly one match — fetch it
ITEM_ID=$(echo "$MATCHES" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
ITEM_TYPE=$(echo "$MATCHES" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['type'])")
ITEM_TITLE=$(echo "$MATCHES" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['title'])")
ITEM_CONTENT=$(echo "$MATCHES" | python3 -c "import sys,json; print(json.load(sys.stdin)[0].get('content', ''))")
ITEM_FILENAME=$(echo "$MATCHES" | python3 -c "import sys,json; f=json.load(sys.stdin)[0].get('filename',''); import os; print(os.path.basename(f) if f else '')")

mkdir -p "$OUTPUT_DIR"

if [ "$ITEM_TYPE" = "note" ]; then
    # Save note as Markdown
    SAFE_NAME=$(safe_filename "$ITEM_TITLE")
    DEST=$(unique_path "$OUTPUT_DIR" "$SAFE_NAME" ".md")
    echo "$ITEM_CONTENT" > "$DEST"
    echo -e "${GREEN}Fetched note:${NC} $DEST"
else
    # Download file
    if [ -n "$ITEM_FILENAME" ]; then
        FNAME="$ITEM_FILENAME"
    else
        FNAME=$(safe_filename "$ITEM_TITLE")
    fi
    NAME="${FNAME%.*}"
    EXT=".${FNAME##*.}"
    if [ "$NAME" = "$FNAME" ]; then EXT=""; fi
    DEST=$(unique_path "$OUTPUT_DIR" "$NAME" "$EXT")
    curl -s -o "$DEST" "$API/items/$ITEM_ID/download"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Fetched file:${NC} $DEST"
    else
        echo -e "${RED}Failed to download file${NC}"
        exit 1
    fi
fi
