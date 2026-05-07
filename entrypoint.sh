#!/bin/sh
# Fix ownership of bind-mounted config.json so appuser can read/write it
chown appuser:appuser /app/config.json 2>/dev/null || true
# Drop privileges and exec the CMD
exec gosu appuser "$@"
