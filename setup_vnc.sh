#!/bin/bash

echo "🖥️ Setting up VNC for easy Facebook login..."

# Update package list
echo "📦 Updating packages..."
apt update -qq

# Install VNC components
echo "🔧 Installing VNC tools..."
apt install -y xvfb x11vnc websockify novnc

# Create novnc symlink if needed
if [ ! -L /usr/share/novnc ]; then
    if [ -d /usr/share/novnc ]; then
        echo "✅ noVNC already available"
    else
        echo "📥 Setting up web VNC..."
        # Try to find novnc installation
        if [ -d /usr/share/novnc ]; then
            echo "✅ noVNC found"
        else
            echo "⚠️ noVNC not found, installing from source..."
            cd /tmp
            git clone https://github.com/novnc/noVNC.git
            mkdir -p /usr/share/novnc
            cp -r noVNC/* /usr/share/novnc/
            rm -rf noVNC
        fi
    fi
fi

# Get server IP
SERVER_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "✅ VNC setup complete!"
echo ""
echo "🎉 Your client can now use Manual Login easily:"
echo "1. Use Telegram: /login → 'Manual Browser'"
echo "2. Bot will provide connection details automatically"
echo ""
echo "📱 Connection options will be:"
echo "• Web browser: http://$SERVER_IP:6080/vnc.html"
echo "• VNC app: $SERVER_IP:5901"
echo ""
echo "🚀 Ready to go!" 