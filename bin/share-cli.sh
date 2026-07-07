#!/bin/bash
# share-cli — unified command-line tool for Personal Share
#
# Usage: share-cli <command> [options] [args]
#
#   share    Create a note, upload a file, or share a directory
#   fetch    Download an item to a local directory       (alias: get)
#   list     List items                                  (alias: ls)
#   delete   Delete an item by partial title match       (alias: rm)
#   help     Show usage (also: -h, --help)
#
# Every command accepts -p/--port PORT (default 9100, or $SHARE_PORT).
# Run `share-cli <command> --help` for command-specific options.

PORT=${SHARE_PORT:-9100}
API=""   # resolved from $PORT by set_api

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# curl defaults: bounded (never hang on a wedged server) and -sS so real
# transport errors still surface (captured into the response for HTTP-code checks).
CURL_OPTS=(-sS --connect-timeout 3 --max-time 60)

set_api() {
    if ! [[ "$PORT" =~ ^[0-9]+$ ]]; then
        echo -e "${RED}Invalid port: $PORT${NC}" >&2
        exit 2
    fi
    API="http://localhost:$PORT/share/api"
}

# ==================== Shared helpers ====================

# Escape a string as a JSON value (quoted). Tolerates invalid UTF-8 so a
# byte-truncated title can never crash the encoder.
json_escape() {
    printf '%s' "$1" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.buffer.read().decode("utf-8","replace")), end="")'
}

# URL-encode a single query-string value.
urlenc() {
    python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$1"
}

# Split a `curl -w "\n%{http_code}"` response (captured with 2>&1) into the
# globals HTTP_CODE and HTTP_BODY. Pure parameter expansion — portable, and
# correct for empty and multi-line bodies.
split_response() {
    local resp="$1"
    HTTP_CODE="${resp##*$'\n'}"
    HTTP_BODY="${resp%$'\n'*}"
}

# Fetch items as JSON. Honors TYPE_FILTER / CATEGORY_FILTER if set by the
# caller. Returns curl's exit code so callers can detect an unreachable server.
fetch_items() {
    local url="$API/items?"
    [ -n "$TYPE_FILTER" ] && url="${url}type=$(urlenc "$TYPE_FILTER")&"
    [ -n "$CATEGORY_FILTER" ] && url="${url}category=$(urlenc "$CATEGORY_FILTER")&"
    curl "${CURL_OPTS[@]}" -f "$url" 2>/dev/null
}

# Safe filename from an arbitrary title (newlines included), never empty.
safe_filename() {
    printf '%s' "$1" | tr '/:*?"<>|\\\n' '_' | tr -s '_' | sed 's/^_//;s/_$//'
}

# Print a non-colliding path: <dir>/<name><ext>, adding _1, _2, ... if needed.
unique_path() {
    local dir="$1" name="$2" ext="$3"
    local path="$dir/$name$ext"
    if [ ! -e "$path" ]; then echo "$path"; return; fi
    local i=1
    while [ -e "$dir/${name}_${i}${ext}" ]; do i=$((i + 1)); done
    echo "$dir/${name}_${i}${ext}"
}

# Resolve a search term to exactly one item.
#   success: prints the single item JSON to stdout, returns 0
#   zero/multiple/error: prints a message to stderr, returns 1
resolve_single_match() {
    local term="$1" items matches count
    items=$(fetch_items) || { echo -e "${RED}Error: cannot reach Personal Share server on port $PORT${NC}" >&2; return 1; }
    if [ -z "$items" ] || [ "$items" = "[]" ]; then
        echo -e "${RED}Error: No items found on server${NC}" >&2
        return 1
    fi
    matches=$(echo "$items" | SC_TERM="$term" python3 -c '
import sys, json, os
try:
    items = json.load(sys.stdin)
except Exception:
    sys.exit(3)
term = os.environ["SC_TERM"].lower()
print(json.dumps([i for i in items if term in i.get("title", "").lower()]))
') || { echo -e "${RED}Error: unexpected response from server${NC}" >&2; return 1; }
    count=$(echo "$matches" | python3 -c 'import sys,json; print(len(json.load(sys.stdin)))' 2>/dev/null)
    if ! [[ "$count" =~ ^[0-9]+$ ]]; then
        echo -e "${RED}Error: unexpected response from server${NC}" >&2
        return 1
    fi
    if [ "$count" -eq 0 ]; then
        echo -e "${RED}Error: No items matching \"$term\"${NC}" >&2
        return 1
    fi
    if [ "$count" -gt 1 ]; then
        echo -e "${YELLOW}Ambiguous: $count items match \"$term\":${NC}" >&2
        echo "$matches" | python3 -c '
import sys, json
for item in json.load(sys.stdin):
    typ = item.get("type", "?")
    title = item.get("title", "(untitled)")
    cat = item.get("category", "")
    cat_str = f" ({cat})" if cat else ""
    print(f"  [{typ}] {title}{cat_str}")
' >&2
        echo "" >&2
        echo "Refine your search to match exactly one item." >&2
        return 1
    fi
    echo "$matches" | python3 -c 'import sys,json; print(json.dumps(json.load(sys.stdin)[0]))'
}

# ==================== share ====================

usage_share() {
    cat <<EOF
Usage: share-cli share [options] <content | file | directory>
       echo "text" | share-cli share [options]

Create a note, upload a file, or share a directory.

Options:
  -t, --title "Title"      Explicit title (default: auto-derived)
  -c, --category "name"    Assign to a category
  -p, --port PORT          Server port (default: 9100)
  -h, --help               Show this help

Pipe input always creates a note, even if it looks like a file path.
EOF
}

cmd_share() {
    local TITLE="" CATEGORY=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -t|--title) [[ $# -ge 2 ]] || { echo -e "${RED}Option $1 requires a value${NC}" >&2; return 1; }; TITLE="$2"; shift 2 ;;
            -c|--category) [[ $# -ge 2 ]] || { echo -e "${RED}Option $1 requires a value${NC}" >&2; return 1; }; CATEGORY="$2"; shift 2 ;;
            -p|--port) [[ $# -ge 2 ]] || { echo -e "${RED}Option $1 requires a value${NC}" >&2; return 1; }; PORT="$2"; shift 2 ;;
            -h|--help) usage_share; return 0 ;;
            --) shift; break ;;
            -*) echo -e "${RED}Unknown option: $1${NC}" >&2; usage_share >&2; return 1 ;;
            *) break ;;
        esac
    done
    set_api

    # Determine input mode: directory, file, args, or pipe
    local FILE_PATH="" CONTENT="" DIR_PATH=""
    if [ $# -gt 0 ]; then
        if [ $# -eq 1 ] && [ -d "$1" ]; then
            DIR_PATH="$(cd "$1" && pwd)"
        elif [ $# -eq 1 ] && [ -f "$1" ]; then
            FILE_PATH="$1"
        else
            CONTENT="$*"
        fi
    elif [ ! -t 0 ]; then
        CONTENT=$(cat)
    else
        usage_share >&2
        return 1
    fi

    # --- Directory sharing ---
    if [ -n "$DIR_PATH" ]; then
        local JSON_PATH RESPONSE NAME
        JSON_PATH=$(json_escape "$DIR_PATH")
        RESPONSE=$(curl "${CURL_OPTS[@]}" -w "\n%{http_code}" -X POST "$API/folders" \
            -H "Content-Type: application/json" \
            -d "{\"target_path\": $JSON_PATH}" 2>&1)
        split_response "$RESPONSE"
        if [ "$HTTP_CODE" = "200" ]; then
            NAME=$(printf '%s' "$HTTP_BODY" | python3 -c 'import sys,json; print(json.load(sys.stdin)["name"])' 2>/dev/null)
            echo -e "${GREEN}Shared folder:${NC} $DIR_PATH (as $NAME)"
        else
            echo -e "${RED}Failed (HTTP $HTTP_CODE):${NC} $HTTP_BODY" >&2
            return 1
        fi
        return 0
    fi

    # --- File upload ---
    if [ -n "$FILE_PATH" ]; then
        local FILENAME DISPLAY_TITLE QF RESPONSE
        FILENAME=$(basename "$FILE_PATH")
        DISPLAY_TITLE="${TITLE:-$FILENAME}"
        # Quote the @path so filenames with spaces/;,"" don't break curl -F parsing.
        QF="${FILE_PATH//\\/\\\\}"; QF="${QF//\"/\\\"}"
        RESPONSE=$(curl "${CURL_OPTS[@]}" -w "\n%{http_code}" -X POST "$API/items/upload" \
            -F "file=@\"$QF\"" \
            --form-string "category=$CATEGORY" \
            --form-string "title=$TITLE" 2>&1)
        split_response "$RESPONSE"
        if [ "$HTTP_CODE" = "200" ]; then
            echo -e "${GREEN}Uploaded:${NC} $DISPLAY_TITLE"
        else
            echo -e "${RED}Failed (HTTP $HTTP_CODE):${NC} $HTTP_BODY" >&2
            return 1
        fi
        return 0
    fi

    # --- Note creation ---
    if [ -z "$TITLE" ]; then
        if printf '%s' "$CONTENT" | head -1 | grep -qE '^https?://'; then
            TITLE=$(printf '%s' "$CONTENT" | head -1 | sed -E 's|https?://([^/]+).*|\1|')
        else
            TITLE=$(printf '%s' "$CONTENT" | head -1 | cut -c1-50)
        fi
    fi

    local JSON_TITLE JSON_CONTENT JSON_CATEGORY RESPONSE
    JSON_TITLE=$(json_escape "$TITLE")
    JSON_CONTENT=$(json_escape "$CONTENT")
    JSON_CATEGORY=$(json_escape "$CATEGORY")
    RESPONSE=$(curl "${CURL_OPTS[@]}" -w "\n%{http_code}" -X POST "$API/items" \
        -H "Content-Type: application/json" \
        -d "{\"title\": $JSON_TITLE, \"content\": $JSON_CONTENT, \"category\": $JSON_CATEGORY}" 2>&1)
    split_response "$RESPONSE"
    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}Shared:${NC} $TITLE"
    else
        echo -e "${RED}Failed (HTTP $HTTP_CODE):${NC} $HTTP_BODY" >&2
        return 1
    fi
}

# ==================== list ====================

usage_list() {
    cat <<EOF
Usage: share-cli list [options]

List recent items (pin marker, type, title, category).

Options:
  --type note|file         Filter by type
  --category "name"        Filter by category
  -p, --port PORT          Server port (default: 9100)
  -h, --help               Show this help
EOF
}

cmd_list() {
    local TYPE_FILTER="" CATEGORY_FILTER=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --type) [[ $# -ge 2 ]] || { echo -e "${RED}Option $1 requires a value${NC}" >&2; return 1; }; TYPE_FILTER="$2"; shift 2 ;;
            --category) [[ $# -ge 2 ]] || { echo -e "${RED}Option $1 requires a value${NC}" >&2; return 1; }; CATEGORY_FILTER="$2"; shift 2 ;;
            -p|--port) [[ $# -ge 2 ]] || { echo -e "${RED}Option $1 requires a value${NC}" >&2; return 1; }; PORT="$2"; shift 2 ;;
            -h|--help) usage_list; return 0 ;;
            *) echo -e "${RED}Unknown option: $1${NC}" >&2; usage_list >&2; return 1 ;;
        esac
    done
    set_api

    local ITEMS
    ITEMS=$(fetch_items) || { echo -e "${RED}Error: cannot reach Personal Share server on port $PORT${NC}" >&2; return 1; }
    if [ -z "$ITEMS" ] || [ "$ITEMS" = "[]" ]; then
        echo "No items found."
        return 0
    fi
    echo "$ITEMS" | python3 -c '
import sys, json
for item in json.load(sys.stdin):
    typ = item.get("type", "?")
    title = item.get("title", "(untitled)")[:50]
    cat = item.get("category", "")
    cat_str = f"({cat})" if cat else ""
    pinned = "*" if item.get("pinned") else " "
    print(f"{pinned} [{typ:4s}]  {title:<50s} {cat_str:<15s}")
'
}

# ==================== fetch ====================

usage_fetch() {
    cat <<EOF
Usage: share-cli fetch [options] <search term>

Fetch one item by partial title match. Notes are saved as Markdown
(title.md); files are downloaded with their original filename. Errors
if zero or multiple items match.

Options:
  -o, --output /path/dir   Output directory (default: current dir)
  -p, --port PORT          Server port (default: 9100)
  -h, --help               Show this help
EOF
}

cmd_fetch() {
    local OUTPUT_DIR="." TYPE_FILTER="" CATEGORY_FILTER=""
    local -a POS=()
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -o|--output) [[ $# -ge 2 ]] || { echo -e "${RED}Option $1 requires a value${NC}" >&2; return 1; }; OUTPUT_DIR="$2"; shift 2 ;;
            -p|--port) [[ $# -ge 2 ]] || { echo -e "${RED}Option $1 requires a value${NC}" >&2; return 1; }; PORT="$2"; shift 2 ;;
            -h|--help) usage_fetch; return 0 ;;
            --) shift; while [[ $# -gt 0 ]]; do POS+=("$1"); shift; done ;;
            -*) echo -e "${RED}Unknown option: $1${NC}" >&2; usage_fetch >&2; return 1 ;;
            *) POS+=("$1"); shift ;;
        esac
    done
    set_api

    local SEARCH_TERM="${POS[*]}"
    if [ -z "$SEARCH_TERM" ]; then
        echo -e "${RED}Error: provide a search term${NC}" >&2
        usage_fetch >&2
        return 1
    fi

    local MATCH
    MATCH=$(resolve_single_match "$SEARCH_TERM") || return 1

    local ID TYPE TITLE CONTENT FILENAME
    ID=$(printf '%s' "$MATCH" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
    TYPE=$(printf '%s' "$MATCH" | python3 -c 'import sys,json; print(json.load(sys.stdin)["type"])')
    TITLE=$(printf '%s' "$MATCH" | python3 -c 'import sys,json; print(json.load(sys.stdin)["title"])')
    CONTENT=$(printf '%s' "$MATCH" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("content", ""))')
    FILENAME=$(printf '%s' "$MATCH" | python3 -c 'import sys,json,os; f=json.load(sys.stdin).get("filename",""); print(os.path.basename(f) if f else "")')

    mkdir -p "$OUTPUT_DIR" || { echo -e "${RED}Cannot create directory: $OUTPUT_DIR${NC}" >&2; return 1; }

    if [ "$TYPE" = "note" ]; then
        local SAFE_NAME DEST
        SAFE_NAME=$(safe_filename "$TITLE")
        [ -z "$SAFE_NAME" ] && SAFE_NAME="untitled"
        DEST=$(unique_path "$OUTPUT_DIR" "$SAFE_NAME" ".md")
        printf '%s\n' "$CONTENT" > "$DEST" || { echo -e "${RED}Failed to write: $DEST${NC}" >&2; return 1; }
        echo -e "${GREEN}Fetched note:${NC} $DEST"
    else
        local FNAME NAME EXT DEST
        if [ -n "$FILENAME" ]; then FNAME="$FILENAME"; else FNAME=$(safe_filename "$TITLE"); fi
        [ -z "$FNAME" ] && FNAME="untitled"
        NAME="${FNAME%.*}"
        EXT=".${FNAME##*.}"
        [ "$NAME" = "$FNAME" ] && EXT=""
        [ -z "$NAME" ] && { NAME="$FNAME"; EXT=""; }
        DEST=$(unique_path "$OUTPUT_DIR" "$NAME" "$EXT")
        if curl "${CURL_OPTS[@]}" -f -o "$DEST" "$API/items/$ID/download" 2>/dev/null; then
            echo -e "${GREEN}Fetched file:${NC} $DEST"
        else
            rm -f "$DEST"
            echo -e "${RED}Failed to download file (server returned an error)${NC}" >&2
            return 1
        fi
    fi
}

# ==================== delete ====================

usage_delete() {
    cat <<EOF
Usage: share-cli delete [options] <search term>

Delete one item by partial title match (same matching as fetch).
Errors if zero or multiple items match; a unique match is deleted
immediately with no confirmation. For file items the server also
removes the file from disk and cleans up a now-empty category.

Options:
  -p, --port PORT          Server port (default: 9100)
  -h, --help               Show this help
EOF
}

cmd_delete() {
    local TYPE_FILTER="" CATEGORY_FILTER=""
    local -a POS=()
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -p|--port) [[ $# -ge 2 ]] || { echo -e "${RED}Option $1 requires a value${NC}" >&2; return 1; }; PORT="$2"; shift 2 ;;
            -h|--help) usage_delete; return 0 ;;
            --) shift; while [[ $# -gt 0 ]]; do POS+=("$1"); shift; done ;;
            -*) echo -e "${RED}Unknown option: $1${NC}" >&2; usage_delete >&2; return 1 ;;
            *) POS+=("$1"); shift ;;
        esac
    done
    set_api

    local SEARCH_TERM="${POS[*]}"
    if [ -z "$SEARCH_TERM" ]; then
        echo -e "${RED}Error: provide a search term${NC}" >&2
        usage_delete >&2
        return 1
    fi

    local MATCH
    MATCH=$(resolve_single_match "$SEARCH_TERM") || return 1

    local ID TYPE TITLE
    ID=$(printf '%s' "$MATCH" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
    TYPE=$(printf '%s' "$MATCH" | python3 -c 'import sys,json; print(json.load(sys.stdin)["type"])')
    TITLE=$(printf '%s' "$MATCH" | python3 -c 'import sys,json; print(json.load(sys.stdin)["title"])')

    local RESPONSE
    RESPONSE=$(curl "${CURL_OPTS[@]}" -w "\n%{http_code}" -X DELETE "$API/items/$ID" 2>&1)
    split_response "$RESPONSE"
    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}Deleted:${NC} [$TYPE] $TITLE"
    else
        echo -e "${RED}Failed (HTTP $HTTP_CODE):${NC} $HTTP_BODY" >&2
        return 1
    fi
}

# ==================== Dispatcher ====================

usage() {
    cat <<EOF
share-cli — Personal Share command-line tool

Usage: share-cli <command> [options] [args]

Commands:
  share    Create a note, upload a file, or share a directory
  fetch    Download an item to a local directory       (alias: get)
  list     List items                                  (alias: ls)
  delete   Delete an item by partial title match       (alias: rm)
  help     Show this help (also: -h, --help)

Global options (accepted by every command):
  -p, --port PORT   Server port (default: 9100, or \$SHARE_PORT)

Run 'share-cli <command> --help' for command-specific options.
EOF
}

CMD="${1:-}"
[ $# -gt 0 ] && shift

case "$CMD" in
    share)          cmd_share "$@" ;;
    fetch|get)      cmd_fetch "$@" ;;
    list|ls)        cmd_list "$@" ;;
    delete|rm)      cmd_delete "$@" ;;
    help|-h|--help) usage ;;
    "")             usage >&2; exit 1 ;;
    *)              echo -e "${RED}Unknown command: $CMD${NC}\n" >&2; usage >&2; exit 1 ;;
esac
