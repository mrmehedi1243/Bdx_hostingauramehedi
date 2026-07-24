#!/bin/bash
cd "$(dirname "$0")"

# Install dependencies if needed
pip install -r requirements.txt -q --break-system-packages --no-input 2>/dev/null

# Use gunicorn for production performance (4 workers, threaded)
exec gunicorn app:app \
  --bind "0.0.0.0:${PORT:-5000}" \
  --workers 4 \
  --threads 4 \
  --worker-class gthread \
  --timeout 120 \
  --keep-alive 5 \
  --access-logfile - \
  --error-logfile - \
  --log-level warning
