# Memory Index

- [pip install on this sandbox](pip-install-externally-managed.md) — always pass `--break-system-packages --no-input` or installs fail with "externally-managed-environment".
- [Flask multi-artifact admin auth testing](flask-admin-curl-testing.md) — login route and dashboard route are often separate paths; use a cookie jar and hit the real dashboard route, not the login route, when curl-testing post-login pages.
