#!/bin/bash
#
# Deploy Personal Share to production
# Usage: ./bin/deploy-prod.sh /path/to/production/directory
#
# Safe to run against both new and existing production directories:
#   - Never overwrites data/content/ (user's shared files)
#   - Never overwrites *.db files
#   - Creates data/content/ directory structure if missing
#   - Only copies files needed to run the service

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -z "$1" ]; then
    echo -e "${RED}Error: Production directory not specified${NC}"
    echo ""
    echo "Usage: $0 /path/to/production/directory"
    echo ""
    echo "Example:"
    echo "  $0 /home/user/share-prod"
    exit 1
fi

PROD_DIR="$1"
PROD_DIR="${PROD_DIR/#\~/$HOME}"
PROD_DIR="$(cd "$(dirname "$PROD_DIR")" 2>/dev/null && pwd)/$(basename "$PROD_DIR")" 2>/dev/null || PROD_DIR="$1"

# Safety: don't deploy to the dev directory
if [ "$PROD_DIR" = "$PROJECT_ROOT" ]; then
    echo -e "${RED}Error: Production directory cannot be the same as development directory${NC}"
    exit 1
fi

echo -e "${GREEN}Deploying Personal Share to production...${NC}"
echo "  Source:  $PROJECT_ROOT"
echo "  Target:  $PROD_DIR"
echo ""

# Create production directory if needed
if [ ! -d "$PROD_DIR" ]; then
    echo -e "${YELLOW}Creating production directory...${NC}"
    mkdir -p "$PROD_DIR"
fi

# ==================== Helper functions ====================

sync_dir() {
    local src="$1"
    local dest="$2"
    local name="$3"

    if [ -d "$src" ]; then
        echo "  Syncing $name..."
        mkdir -p "$dest"
        rsync -a --delete \
            --exclude='__pycache__' \
            --exclude='*.pyc' \
            --exclude='*.pyo' \
            "$src/" "$dest/"
    fi
}

copy_file() {
    local src="$1"
    local dest="$2"
    local name="$3"

    if [ -f "$src" ]; then
        echo "  Copying $name..."
        cp "$src" "$dest"
    fi
}

echo -e "${GREEN}Copying application files...${NC}"

# Source code
sync_dir "$PROJECT_ROOT/src" "$PROD_DIR/src" "src/"

# Public assets (frontend)
sync_dir "$PROJECT_ROOT/public" "$PROD_DIR/public" "public/"

# Bin scripts (exclude deploy script itself)
echo "  Syncing bin/..."
mkdir -p "$PROD_DIR/bin"
for script in "$PROJECT_ROOT/bin/"*; do
    script_name="$(basename "$script")"
    if [ "$script_name" != "deploy-prod.sh" ]; then
        cp "$script" "$PROD_DIR/bin/"
        chmod +x "$PROD_DIR/bin/$script_name"
    fi
done

# Requirements
copy_file "$PROJECT_ROOT/requirements.txt" "$PROD_DIR/requirements.txt" "requirements.txt"

# Claude Code skills — copy to prod, then symlink to ~/.claude/skills/
# Clean up old skill name if present
for old_name in share-note; do
    old_link="$HOME/.claude/skills/$old_name"
    if [ -L "$old_link" ] || [ -d "$old_link" ]; then
        echo "  Removing old skill: $old_name"
        rm -rf "$old_link"
    fi
    old_prod="$PROD_DIR/skills/$old_name"
    if [ -d "$old_prod" ]; then
        rm -rf "$old_prod"
    fi
done

deploy_skill() {
    local skill_name="$1"
    local src_dir="$PROJECT_ROOT/skills/$skill_name"
    local prod_dir="$PROD_DIR/skills/$skill_name"
    local link_dir="$HOME/.claude/skills/$skill_name"

    if [ ! -d "$src_dir" ]; then return; fi

    echo "  Syncing $skill_name skill..."
    mkdir -p "$prod_dir"
    sed "s|\$SHARE_DIR|$PROD_DIR|g" "$src_dir/SKILL.md" > "$prod_dir/SKILL.md"

    if [ -L "$link_dir" ]; then
        rm "$link_dir"
    elif [ -d "$link_dir" ]; then
        rm -rf "$link_dir"
    fi
    ln -s "$prod_dir" "$link_dir"
    echo "  Linked $link_dir -> $prod_dir"
}

deploy_skill "personal-share"
deploy_skill "personal-fetch"

echo ""

# ==================== Data directory (safe) ====================

echo -e "${GREEN}Ensuring data directory structure...${NC}"

# Create data/ and data/content/ if they don't exist
# NEVER delete or overwrite anything under data/
mkdir -p "$PROD_DIR/data/content"
echo "  data/content/ ready"

# Verify nothing was touched
if [ -f "$PROD_DIR/data/share.db" ]; then
    echo -e "  ${YELLOW}Existing database preserved: data/share.db${NC}"
fi

content_count=$(find "$PROD_DIR/data/content" -type f 2>/dev/null | wc -l)
if [ "$content_count" -gt 0 ]; then
    echo -e "  ${YELLOW}Existing content preserved: $content_count files in data/content/${NC}"
fi

echo ""
echo -e "${GREEN}Deployment complete!${NC}"
echo ""

# First-time setup instructions (only if no venv exists)
if [ ! -d "$PROD_DIR/venv" ]; then
    echo -e "${YELLOW}First-time setup:${NC}"
    echo ""
    echo "  cd $PROD_DIR"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    echo "  ./bin/server.sh start"
    echo ""
else
    echo -e "${YELLOW}To restart with new code:${NC}"
    echo ""
    echo "  cd $PROD_DIR"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt   # if deps changed"
    echo "  ./bin/server.sh restart"
    echo ""
fi
