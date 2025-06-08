#!/usr/bin/env bash
# Install and enable systemd services for Bonfire
set -euo pipefail

UNIT_DIR=/etc/systemd/system
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

for service in systemd/*.service; do
    sudo cp "$service" "$UNIT_DIR/"
    unit_name=$(basename "$service")
    sudo systemctl enable "$unit_name"
    sudo systemctl restart "$unit_name"
    echo "Installed $unit_name"
done

sudo systemctl daemon-reload

