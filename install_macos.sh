#!/bin/bash

# Exit on error
set -e

echo "Installing AlterClip..."

# Check if running as root
if [ "$(id -u)" -ne 0 ]; then 
    echo "Please run with sudo"
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

# Create launchd plist file
PLIST_FILE="/Library/LaunchDaemons/com.alterclip.plist"
cat > $PLIST_FILE <<EOL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.alterclip</string>
    <key>ProgramArguments</key>
    <array>
        <string>$SCRIPT_DIR/venv/bin/python</string>
        <string>$SCRIPT_DIR/alterclip.py</string>
        <string>--web</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$SCRIPT_DIR/alterclip.log</string>
    <key>StandardErrorPath</key>
    <string>$SCRIPT_DIR/alterclip_error.log</string>
    <key>WorkingDirectory</key>
    <string>$SCRIPT_DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>$SCRIPT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
EOL

# Set proper permissions
chown root:wheel $PLIST_FILE
chmod 644 $PLIST_FILE

# Load and start the service
launchctl load -w $PLIST_FILE
launchctl start com.alterclip

echo "Installation complete!"
echo "AlterClip is now running and will start on boot."
echo "You can access the web interface at http://localhost:5000"
echo "To check the status: sudo launchctl list | grep alterclip"
echo "To view logs: tail -f $SCRIPT_DIR/alterclip.log"
