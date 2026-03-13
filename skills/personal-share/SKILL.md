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
- For other text: use the first 50 characters

## Implementation

Use the share CLI at the Personal Share project:

```bash
# Note with auto-derived title:
/home/jtiisto/dev/share/bin/personal-share.sh "Content here"

# Note with explicit title:
/home/jtiisto/dev/share/bin/personal-share.sh -t "Title Here" "Content here"

# Note with category:
/home/jtiisto/dev/share/bin/personal-share.sh -c "links" "https://example.com"

# File upload:
/home/jtiisto/dev/share/bin/personal-share.sh /path/to/file.pdf

# File upload with category and title:
/home/jtiisto/dev/share/bin/personal-share.sh -c "docs" -t "Manual" /path/to/file.pdf

# Multi-line content via pipe:
echo "line1
line2" | /home/jtiisto/dev/share/bin/personal-share.sh -t "Title"
```

The server runs on port 9100 (production). If the user says "test" or you know the test server is running, use `-p 9101`.

## Steps

1. Parse the user's message to extract the title, category, and content/file path
2. Run the share CLI command using Bash
3. Report success or failure briefly

## Examples

User: "share this url to my mobile: https://example.com/article"
→ `/home/jtiisto/dev/share/bin/personal-share.sh "https://example.com/article"`

User: "share this as a note in the links category: https://docs.python.org/3/"
→ `/home/jtiisto/dev/share/bin/personal-share.sh -c "links" "https://docs.python.org/3/"`

User: "/personal-share -c recipes Grandma's cookie recipe: mix flour and sugar"
→ `/home/jtiisto/dev/share/bin/personal-share.sh -c "recipes" "Grandma's cookie recipe: mix flour and sugar"`

User: "share this file to my phone: @/home/jtiisto/docs/report.pdf"
→ `/home/jtiisto/dev/share/bin/personal-share.sh /home/jtiisto/docs/report.pdf`

User: "share this pdf under docs: @/tmp/manual.pdf"
→ `/home/jtiisto/dev/share/bin/personal-share.sh -c "docs" /tmp/manual.pdf`
