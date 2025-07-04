#!/bin/bash

# Exit on error
set -e

echo "Installing AlterClip..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use sudo)"
    exit 1
fi

# Install required system packages
if command -v apt-get &> /dev/null; then
    apt-get update
    apt-get install -y python3-venv python3-pip
elif command -v dnf &> /dev/null; then
    dnf install -y python3-venv python3-pip
elif command -v yum &> /dev/null; then
    yum install -y python3-venv python3-pip
else
    echo "Package manager not supported. Please install python3-venv and python3-pip manually."
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create systemd service file
SERVICE_FILE="/etc/systemd/system/alterclip.service"
cat > $SERVICE_FILE <<EOL
[Unit]
Description=AlterClip Clipboard Manager
After=network.target

[Service]
Type=simple
User=$SUDO_USER
WorkingDirectory=$SCRIPT_DIR
Environment="PATH=$SCRIPT_DIR/venv/bin:$PATH"
ExecStart=$SCRIPT_DIR/venv/bin/python $SCRIPT_DIR/alterclip.py --web
Restart=always

[Install]
WantedBy=multi-user.target
EOL

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable alterclip.service
systemctl start alterclip.service

echo "Installation complete! AlterClip is now running and will start on boot.
echo "You can access the web interface at http://localhost:5000"
echo "To check the status: sudo systemctl status alterclip"
echo "To view logs: sudo journalctl -u alterclip -f"
