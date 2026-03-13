#!/bin/bash
#
# Setup Tailscale path-based routing for Wellness + Share apps
# Requires: sudo
#
# Result:
#   :9443/wellness/ -> localhost:9000 (Wellness)
#   :9443/share/    -> localhost:9100 (Share)
#
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}This script must be run with sudo${NC}"
    exit 1
fi

echo -e "${YELLOW}Current Tailscale serve config:${NC}"
tailscale serve status
echo ""

# Step 1: Remove old entries
echo -e "${GREEN}Removing old serve entries...${NC}"
tailscale serve --https 9443 off 2>/dev/null || true
tailscale serve --https 9444 off 2>/dev/null || true

# Step 2: Add path-based routing on :9443
echo -e "${GREEN}Adding /wellness -> localhost:9000...${NC}"
tailscale serve --https 9443 --set-path /wellness --bg http://localhost:9000

echo -e "${GREEN}Adding /share -> localhost:9100...${NC}"
tailscale serve --https 9443 --set-path /share --bg http://localhost:9100

echo ""
echo -e "${YELLOW}Updated Tailscale serve config:${NC}"
tailscale serve status

HOSTNAME=$(tailscale status --self --peers=false --json 2>/dev/null | python3 -c 'import sys,json; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))' 2>/dev/null || echo 'your-hostname')

echo ""
echo -e "${GREEN}Done! Apps available at:${NC}"
echo "  Wellness: https://${HOSTNAME}:9443/wellness/"
echo "  Share:    https://${HOSTNAME}:9443/share/"
