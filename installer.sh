#!/usr/bin/env bash
# Installer script for DevOps Chaos Sandbox
# Resolves #1.

set -euo pipefail

# Ensure running as root
if [ "$EUID" -ne 0 ]; then
  echo "ERROR: Please run this installer as root (sudo bash installer.sh)"
  exit 1
fi

echo "=========================================================="
echo "          INSTALLING GRADUATED CHAOS SANDBOX"
echo "=========================================================="

INSTALL_DIR="/opt/chaos-sandbox"
CONFIG_FILE="/etc/chaos-sandbox.env"

# Create directories
mkdir -p "$INSTALL_DIR/scenarios"
chmod 755 "$INSTALL_DIR"

# Prompt for configs if file doesn't exist
if [ ! -f "$CONFIG_FILE" ]; then
  echo "--- Configuration setup ---"
  read -rp "Enter Telegram Bot Token: " TELEGRAM_BOT_TOKEN
  read -rp "Enter Telegram Chat ID: " TELEGRAM_CHAT_ID
  read -rp "Enter Target Application Health URL (e.g. http://localhost:5000/health): " TARGET_APP_URL

  cat <<EOF > "$CONFIG_FILE"
TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID="$TELEGRAM_CHAT_ID"
TARGET_APP_URL="$TARGET_APP_URL"
EOF
  chmod 600 "$CONFIG_FILE"
  echo "Configuration written to $CONFIG_FILE"
else
  echo "Configuration file already exists at $CONFIG_FILE"
fi

# Copy script files (assuming run from cloned repo folder, fallback to default templates if not)
if [ -f "chaos_scheduler.py" ]; then
  cp chaos_scheduler.py "$INSTALL_DIR/chaos_scheduler.py"
  cp chaos_alerts.py "$INSTALL_DIR/chaos_alerts.py"
  cp -r scenarios/* "$INSTALL_DIR/scenarios/"
else
  echo "WARNING: Executing standalone. Make sure to download files into $INSTALL_DIR manually."
fi

# Make scripts executable
chmod 755 "$INSTALL_DIR"/*.py || true
chmod 755 "$INSTALL_DIR"/scenarios/*.sh || true

# --- Create systemd service for chaos_alerts ---
echo "Configuring systemd service for chaos_alerts..."
cat <<EOF > /etc/systemd/system/chaos-alerts.service
[Unit]
Description=Chaos Sandbox Alerting Daemon
After=network.target

[Service]
Type=simple
EnvironmentFile=$CONFIG_FILE
ExecStart=/usr/bin/python3 $INSTALL_DIR/chaos_alerts.py
Restart=always
RestartSec=10s
User=root

[Install]
WantedBy=multi-user.target
EOF

# --- Create systemd service for chaos_scheduler ---
echo "Configuring systemd service for chaos_scheduler..."
cat <<EOF > /etc/systemd/system/chaos-scheduler.service
[Unit]
Description=Chaos Sandbox Scheduler Task
After=network.target

[Service]
Type=oneshot
EnvironmentFile=$CONFIG_FILE
ExecStart=/usr/bin/python3 $INSTALL_DIR/chaos_scheduler.py
User=root
EOF

# --- Create systemd timer for chaos_scheduler ---
echo "Configuring systemd timer for chaos_scheduler..."
cat <<EOF > /etc/systemd/system/chaos-scheduler.timer
[Unit]
Description=Trigger Chaos Scheduler every 30 minutes

[Timer]
OnCalendar=*:0/30
Persistent=true

[Install]
WantedBy=timers.target
EOF

# Reload and enable services
echo "Starting services..."
systemctl daemon-reload
systemctl enable --now chaos-alerts.service
systemctl enable --now chaos-scheduler.timer

echo "=========================================================="
echo "   INSTALLATION COMPLETE. CHAOS SANDBOX IS ACTIVE!"
echo "=========================================================="
