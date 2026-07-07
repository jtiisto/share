---
name: personal-delete
description: Delete a note or file from the Personal Share app. Triggers on phrases like "delete from share", "remove that note from share", "delete the file I shared", "remove it from my personal share".
user-invocable: true
allowed-tools: Bash($SHARE_DIR/bin/share-cli.sh:*)
---

# Personal Delete Skill

Delete a note or file from the Personal Share app. The item is matched by partial title and removed via the API; the change appears on all connected devices in real-time. **There is no undo** — always show the matched item and wait for the user's explicit confirmation before deleting.

## How to use

The user describes the item to delete — by title, description, or type. Identify the single matching item, show it to the user, wait for an explicit "yes", then delete it. This skill deletes **notes and files only** (see Scope & limits).

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
2. Identify the single item that best matches the user's request.
3. If zero or multiple plausible items match, ask the user which one — do **not** guess, and do **not** delete.
4. Show the matched item as `[type] Title (category)` and **STOP**. Wait for the user's explicit confirmation in their **next message** before deleting. Never run `list` and `delete` in the same turn — not even when invoked as `/personal-delete <term>`.
5. Only after the user confirms, delete it using a term copied **verbatim** from the confirmed item's title (do not retype from memory — a typo could uniquely match a *different* item):
   ```bash
   $SHARE_DIR/bin/share-cli.sh delete "unique part of the confirmed title"
   ```
6. Report what was deleted (the CLI prints `Deleted: [type] Title`).

## Scope & limits

- Deletes **notes and files only**. It cannot remove **shared folders** (the Folders tab / `data/folders/` symlinks). If the user asks to delete or unshare a *folder*, tell them to unshare it from the app's Folders tab.
- Only ever run the `share-cli.sh` commands documented in this skill. Never construct other shell commands (e.g. a raw `curl -X DELETE …`) to accomplish a deletion — if `share-cli.sh` can't do it, stop and tell the user.

## Examples

User: "delete the cookie recipe from share"
→ `$SHARE_DIR/bin/share-cli.sh list --type note`, find the item, then show it and ask:
  "Delete `[note] Cookie Recipe (recipes)`? (yes/no)" — wait for the user's reply, and only on "yes":
  `$SHARE_DIR/bin/share-cli.sh delete "cookie recipe"`

User: "remove that PDF I shared earlier"
→ `$SHARE_DIR/bin/share-cli.sh list --type file`, identify it, show it and wait for confirmation, then:
  `$SHARE_DIR/bin/share-cli.sh delete "report.pdf"`

User: "delete the folder I shared"
→ This skill can't delete folders. Tell the user to unshare it from the app's Folders tab; do not run any API/curl command.
