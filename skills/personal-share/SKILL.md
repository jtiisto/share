---
name: personal-share
description: Share a note, URL, text, or file to the Personal Share app so it appears on mobile and laptop. Triggers on phrases like "share this to my mobile", "send this note to my phone", "share this URL as a note", "share this file".
user-invocable: true
allowed-tools: Bash
---

# Personal Share Skill

Share a note or file to the Personal Share app running on the server. The item will appear on all connected devices (mobile, laptop) in real-time via WebSocket.

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
- For directories: use the directory name
- For other text: use the first 50 characters

## Implementation

Use the share CLI at the Personal Share project:

```bash
# Note with auto-derived title:
$SHARE_DIR/bin/personal-share.sh "Content here"

# Note with explicit title:
$SHARE_DIR/bin/personal-share.sh -t "Title Here" "Content here"

# Note with category:
$SHARE_DIR/bin/personal-share.sh -c "links" "https://example.com"

# File upload:
$SHARE_DIR/bin/personal-share.sh /path/to/file.pdf

# File upload with category and title:
$SHARE_DIR/bin/personal-share.sh -c "docs" -t "Manual" /path/to/file.pdf

# Share a directory (appears in Folders tab):
$SHARE_DIR/bin/personal-share.sh /path/to/directory

# Multi-line content via pipe:
echo "line1
line2" | $SHARE_DIR/bin/personal-share.sh -t "Title"
```

The server runs on port 9100 (production). If the user says "test" or you know the test server is running, use `-p 9101`.

## Steps

1. Parse the user's message to extract the title, category, and content/file path
2. Run the share CLI command using Bash
3. Report success or failure briefly

## Examples

User: "share this url to my mobile: https://example.com/article"
→ `$SHARE_DIR/bin/personal-share.sh "https://example.com/article"`

User: "share this as a note in the links category: https://docs.python.org/3/"
→ `$SHARE_DIR/bin/personal-share.sh -c "links" "https://docs.python.org/3/"`

User: "/personal-share -c recipes Grandma's cookie recipe: mix flour and sugar"
→ `$SHARE_DIR/bin/personal-share.sh -c "recipes" "Grandma's cookie recipe: mix flour and sugar"`

User: "share this file to my phone: @~/docs/report.pdf"
→ `$SHARE_DIR/bin/personal-share.sh ~/docs/report.pdf`

User: "share this pdf under docs: @/tmp/manual.pdf"
→ `$SHARE_DIR/bin/personal-share.sh -c "docs" /tmp/manual.pdf`

User: "share this folder so I can browse it on my phone: ~/dev/project"
→ `$SHARE_DIR/bin/personal-share.sh ~/dev/project`
