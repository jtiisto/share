---
name: personal-fetch
description: Fetch a file or note from the Personal Share app to a local directory. Triggers on phrases like "fetch from share", "download from share", "get that file from share", "pull the note from share".
user-invocable: true
allowed-tools: Bash
---

# Personal Fetch Skill

Fetch a file or note from the Personal Share app to a local directory. Notes are saved as Markdown files. Files are downloaded with their original filename.

## How to use

The user describes what they want to fetch — by title, description, or type. They may also specify an output directory.

## Arguments

Arguments are parsed as: `/personal-fetch [search term or description]`

Optional:
- `-o /path/to/dir` — output directory (default: current working directory)

## Implementation

Use the fetch CLI at the Personal Share project:

```bash
# List items to find the right one:
$SHARE_DIR/bin/personal-fetch.sh --list

# List only files or notes:
$SHARE_DIR/bin/personal-fetch.sh --list --type file
$SHARE_DIR/bin/personal-fetch.sh --list --type note

# Fetch by title match:
$SHARE_DIR/bin/personal-fetch.sh "search term"

# Fetch to a specific directory:
$SHARE_DIR/bin/personal-fetch.sh -o /tmp "search term"
```

The server runs on port 9100 (production). If the user says "test" or you know the test server is running, use `-p 9101`.

## Steps

1. First, list items to find what the user is looking for:
   ```bash
   $SHARE_DIR/bin/personal-fetch.sh --list
   ```
2. Identify the best match for the user's request from the list
3. If the match is ambiguous (multiple plausible items), ask the user which one they want
4. Fetch the item using a specific enough search term to get exactly one match:
   ```bash
   $SHARE_DIR/bin/personal-fetch.sh -o /path/to/dir "exact title or unique part"
   ```
5. Report the saved file path

## Examples

User: "fetch the cookie recipe from share"
→ First: `$SHARE_DIR/bin/personal-fetch.sh --list --type note`
→ Find the recipe, then: `$SHARE_DIR/bin/personal-fetch.sh "cookie recipe"`

User: "download the PDF I shared earlier to /tmp"
→ First: `$SHARE_DIR/bin/personal-fetch.sh --list --type file`
→ Then: `$SHARE_DIR/bin/personal-fetch.sh -o /tmp "report.pdf"`

User: "/personal-fetch deploy reminder"
→ `$SHARE_DIR/bin/personal-fetch.sh "deploy reminder"`
