---
name: pip install externally-managed-environment
description: pip installs in this Replit sandbox fail unless flags are passed; applies to any Python auto-install code paths (upload handlers, setup scripts).
---

`pip install` (including inside app code that auto-installs `requirements.txt` on upload) fails with `error: externally-managed-environment` unless invoked with `--break-system-packages --no-input`.

**Why:** The system Python here is marked externally-managed (PEP 668), so plain `pip install` is blocked by default. This bit a Telegram-bot upload feature where one install code path had the flags and another (auto-install after upload) didn't, causing installs to silently fail only on that path.

**How to apply:** Whenever writing or reviewing code/scripts that call `pip install` (venv-free), always include `--break-system-packages --no-input`. When debugging "works in one place but not another" pip failures, check for this flag mismatch across code paths first.
