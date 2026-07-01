---
name: personal-delete
description: Delete a note or file from the Personal Share app. Triggers on phrases like "delete from share", "remove that note from share", "delete the file I shared", "remove it from my personal share".
user-invocable: true
allowed-tools: Bash
---

# Personal Delete Skill

Delete a note or file from the Personal Share app. The item is matched by partial title and removed via the API; the change appears on all connected devices in real-time. **There is no undo** — always confirm the exact item with the user before deleting.

## How to use

The user describes the item to delete — by title, description, or type. Identify the single matching item, confirm it with the user, then delete it.

## Arguments

Arguments are parsed as: `/personal-delete [search term or description]`

Optional:
- `-p 9101` — target the test server instead of production

## Implementation

Use the `list` and `delete` subcommands of the share CLI at the Personal Share project:

```bash
# Find the item first (to confirm the right one):
$SHARE_DIR/bin/share-cli.sh list

# Delete by partial title match (aborts if zero or multiple match):
$SHARE_DIR/bin/share-cli.sh delete "search term"
```

The server runs on port 9100 (production). If the user says "test" or you know the test server is running, use `-p 9101`.

`delete` matches on partial title. If the term matches zero or multiple items it prints the matches and aborts without deleting anything, so a specific term is required to remove exactly one item.

## Steps

1. List items to find what the user means:
   ```bash
   $SHARE_DIR/bin/share-cli.sh list
   ```
2. Identify the single item that matches the user's request.
3. If multiple plausible items match, ask the user which one — do **not** guess.
4. **Confirm the exact item** (title + type) with the user before deleting — there is no undo.
5. Delete it using a specific enough term to match exactly one item:
   ```bash
   $SHARE_DIR/bin/share-cli.sh delete "exact title or unique part"
   ```
6. Report what was deleted (the CLI prints `Deleted: [type] Title`).

## Examples

User: "delete the cookie recipe from share"
→ First: `$SHARE_DIR/bin/share-cli.sh list --type note`
→ Confirm the match, then: `$SHARE_DIR/bin/share-cli.sh delete "cookie recipe"`

User: "remove that PDF I shared earlier"
→ First: `$SHARE_DIR/bin/share-cli.sh list --type file`
→ Confirm the match, then: `$SHARE_DIR/bin/share-cli.sh delete "report.pdf"`

User: "/personal-delete deploy reminder"
→ Confirm the match, then: `$SHARE_DIR/bin/share-cli.sh delete "deploy reminder"`
