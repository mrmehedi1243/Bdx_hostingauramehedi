---
name: Hosting persistence and restart recovery
description: T10-MEHEDI panel data and hosted processes must survive managed artifact restarts.
---

Panel metadata and uploaded files are kept under the persistent data root, while
hosted process state is reconstructed from the panels table after the web
process starts. The managed artifact can receive SIGTERM during routine
restarts, so a 24/7 host must not rely on the in-memory process map alone.

**Why:** Managed artifact logs show periodic SIGTERM/restart cycles; without
boot resume, panels marked running appear offline even though their records and
files still exist.

**How to apply:** Keep explicit admin ban/delete as the only destructive
controls, preserve panel records/files across expiry and app restarts, enable
SQLite WAL/busy timeout, and auto-restart unexpected child-process exits.