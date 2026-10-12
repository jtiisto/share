---
name: personal-share
description: Share a note, URL, text, or file to the Personal Share app so it appears on mobile and laptop. Triggers on phrases like "share this to my mobile", "send this note to my phone", "share this URL as a note", "share this file".
user-invocable: true
allowed-tools: Bash
---

# Personal Share Skill

Share a note or file to the Personal Share app. The server may be on another machine; the item will appear on all connected devices (mobile, laptop) in real-time via WebSocket.

## How to use

The user provides content to share — a URL, text snippet, command, file path, or any short content. They may also provide a title and/or category.

## Arguments

Arguments are parsed as: `/personal-share [content or file path]`

Optional flags:
- `-t "Title"` — explicit title
- `-c "category"` — assign to a category

If no explicit title is given:
- For URLs: use the domain as the title
- For files: use the filename
- For other text: use the first 50 characters

## Implementation

Use the `share` subcommand of the share CLI at the Personal Share project:

```bash
# Note with auto-derived title:
$SHARE_DIR/bin/share-cli.sh share "Content here"

# Note with explicit title:
$SHARE_DIR/bin/share-cli.sh share -t "Title Here" "Content here"

# Note with category:
$SHARE_DIR/bin/share-cli.sh share -c "links" "https://example.com"

# File upload:
$SHARE_DIR/bin/share-cli.sh share /path/to/file.pdf

# File upload with category and title:
$SHARE_DIR/bin/share-cli.sh share -c "docs" -t "Manual" /path/to/file.pdf

# Multi-line content via pipe:
echo "line1
line2" | $SHARE_DIR/bin/share-cli.sh share -t "Title"
```

The server location comes from `$SHARE_URL` when it is non-empty (a remote client), otherwise `http://localhost:9100`. Pass `--url http://localhost:9101` only when the user says "test" or you know a local test server is running. There is no port flag.

## Steps

1. Parse the user's message to extract the title, category, and content/file path
2. Run the share CLI command using Bash
3. Report success or failure briefly

## Examples

User: "share this url to my mobile: https://example.com/article"
→ `$SHARE_DIR/bin/share-cli.sh share "https://example.com/article"`

User: "share this as a note in the links category: https://docs.python.org/3/"
→ `$SHARE_DIR/bin/share-cli.sh share -c "links" "https://docs.python.org/3/"`

User: "/personal-share -c recipes Grandma's cookie recipe: mix flour and sugar"
→ `$SHARE_DIR/bin/share-cli.sh share -c "recipes" "Grandma's cookie recipe: mix flour and sugar"`

User: "share this file to my phone: @~/docs/report.pdf"
→ `$SHARE_DIR/bin/share-cli.sh share ~/docs/report.pdf`

User: "share this pdf under docs: @/tmp/manual.pdf"
→ `$SHARE_DIR/bin/share-cli.sh share -c "docs" /tmp/manual.pdf`

User: "share this folder so I can browse it on my phone: ~/dev/project"
→ Folders are not supported. Tell the user to share individual files instead; do not run a command.
