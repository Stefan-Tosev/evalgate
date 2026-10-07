# Session economics

One entry per session, newest at the bottom. Only what would change how
the next session is run.

## 2026-10-07 — git init and first push

- **Commit messages on PowerShell 5.1:** piping a here-string to
  `git commit -F -` failed ("does not have any commits yet"). Write the
  message to a scratchpad file and use `git commit -F <file>` first time.
- **Read with Read, not `Get-Content`, any file you will rewrite.** Dumping
  NEXT.md via PowerShell cost the tokens but did not count as a read, so
  the later `Write` was refused and the file was read again.
- **Wait for CI with one background `until` loop**, not polling turns —
  one notification, near-zero context.
