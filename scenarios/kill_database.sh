#!/usr/bin/env bash
# PostgreSQL failure injection scenario
# Resolves #4.

echo "--- Injecting PostgreSQL outage scenario ---"

# 1. Target Docker container
if command -v docker &> /dev/null; then
  # Look for postgres container
  pg_container=$(docker ps -q -f "name=postgres" -f "name=pg" | head -n1)
  if [ -n "$pg_container" ]; then
    echo "Found PostgreSQL Docker container: $pg_container"
    echo "Disabling container auto-restart..."
    docker update --restart=no "$pg_container"
    echo "Stopping container..."
    docker stop "$pg_container"
    echo "PostgreSQL Docker outage injected."
    exit 0
  fi
fi

# 2. Target systemd service
if systemctl list-unit-files | grep -q "postgresql.service"; then
  echo "Found PostgreSQL systemd service."
  echo "Disabling service daemon..."
  systemctl disable postgresql
  echo "Stopping service daemon..."
  systemctl stop postgresql
  echo "PostgreSQL systemd outage injected."
  exit 0
fi

echo "WARNING: No active PostgreSQL containers or systemd services detected."
exit 1
