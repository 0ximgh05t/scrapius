#!/bin/bash

echo "🐧 SCRAPIUS - Linux Setup Script"
echo "================================"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found! Installing..."
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv
fi

echo "✅ Python found"
python3 --version

# Install Chrome if not present
if ! command -v google-chrome &> /dev/null; then
    echo "📦 Installing Google Chrome..."
    wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
    sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
    sudo apt update
    sudo apt install -y google-chrome-stable
fi

echo "✅ Chrome installed"
google-chrome --version

# Create virtual environment
echo ""
echo "📦 Creating virtual environment..."
python3 -m venv venv
if [ $? -ne 0 ]; then
    echo "❌ Failed to create virtual environment"
    exit 1
fi

# Activate virtual environment
echo "✅ Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "📦 Upgrading pip..."
python -m pip install --upgrade pip

# Install requirements
echo ""
echo "📦 Installing dependencies..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies"
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "📝 Creating .env file..."
    cp .env.example .env
    
    # Set Linux-specific Chrome settings
    sed -i 's|# CHROME_USER_DATA_DIR=/home/$USER/.config/google-chrome|CHROME_USER_DATA_DIR=/home/'$USER'/.config/google-chrome|' .env
    sed -i 's|# CHROME_PROFILE_DIR=Default|CHROME_PROFILE_DIR=Default|' .env
    sed -i 's|# CHROME_EXECUTABLE_PATH=/usr/bin/google-chrome|CHROME_EXECUTABLE_PATH=/usr/bin/google-chrome|' .env
    sed -i 's|# CHROME_ARGS=--headless,--no-sandbox,--disable-dev-shm-usage,--disable-gpu,--disable-extensions,--disable-plugins,--remote-debugging-port=9222|CHROME_ARGS=--headless,--no-sandbox,--disable-dev-shm-usage,--disable-gpu,--disable-extensions,--disable-plugins,--remote-debugging-port=9222|' .env
    
    echo "✅ Created .env file with Linux settings"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env file with your API keys:"
    echo "   - OPENAI_API_KEY"
    echo "   - TELEGRAM_BOT_TOKEN" 
    echo "   - ALLOWED_CHAT_IDS"
fi

# Test installation
echo ""
echo "🧪 Testing installation..."
python -c "import selenium, requests, openai; print('✅ All packages imported successfully!')"
if [ $? -ne 0 ]; then
    echo "❌ Package import test failed"
    exit 1
fi

echo ""
echo "🎉 Linux setup completed successfully!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your API keys: nano .env"
echo "2. Copy your fb_cookies.json file (if you have one)"
echo "3. Activate virtual environment: source venv/bin/activate"
echo "4. Run the bot: python main.py"
echo "5. Use Telegram /login -> 'Use Existing Cookies' or 'Import Cookies'"
echo ""
echo "For headless servers, the bot will run without GUI!"
echo ""
