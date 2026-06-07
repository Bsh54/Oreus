#!/bin/bash
# Oreus — initial server setup script (Ubuntu 22.04 / Azure VM)
# Run once as your deploy user after cloning the repo.
set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Installing system dependencies"
sudo apt-get update -qq
sudo apt-get install -y ffmpeg python3-pip python3-venv

echo "==> Creating Python virtual environment"
cd "$REPO_DIR"
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt

echo "==> Creating runtime directories"
mkdir -p uploads outputs jobs fonts

echo "==> Installing systemd service"
sudo cp deploy/oreus.service /etc/systemd/system/oreus.service
sudo systemctl daemon-reload
sudo systemctl enable oreus.service

echo ""
echo "Done. Before starting the service:"
echo "  1. Add your fonts to fonts/ (arial.ttf, arialbd.ttf)"
echo "  2. Set DS2_API and OREUS_ADMIN_KEY in /etc/systemd/system/oreus.service"
echo "  3. sudo systemctl start oreus.service"
echo "  4. sudo systemctl status oreus.service"
