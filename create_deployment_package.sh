#!/bin/bash

echo "🚀 Creating Scrapius Windows Deployment Package"
echo "==============================================="

# Create deployment directory
rm -rf scrapius_deployment
mkdir scrapius_deployment

echo "📦 Copying essential files..."

# Copy main application files
cp main.py config.py requirements.txt .gitignore insights.db scrapius_deployment/

# Copy directories
echo "📁 Copying directories..."
cp -r ai bot database notifier scraper scrapius_deployment/

# Copy Windows setup files
cp setup_windows.bat README_WINDOWS.md WINDOWS_INSTALLATION_GUIDE.md scrapius_deployment/

# Create empty .env template
cat > scrapius_deployment/.env.example << 'EOF'
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
ALLOWED_CHAT_IDS=your_chat_id_here

# Chrome Configuration (Windows paths)
CHROME_USER_DATA_DIR=C:\Users\%USERNAME%\AppData\Local\Google\Chrome\User Data
CHROME_PROFILE_DIR=Default

# Bot Settings
BOT_PROMPT_SYSTEM=You are a helpful assistant that filters Facebook posts.
BOT_PROMPT_USER=Send only posts where people are looking for marketing services
BOT_POLL_SECONDS=600

# Facebook Credentials (Optional)
FB_USER=your_facebook_email@example.com
FB_PASS=your_facebook_password
EOF

# Create deployment README
cat > scrapius_deployment/README.md << 'EOF'
# 🤖 **Scrapius Facebook Bot - Ready for Windows Deployment**

## Quick Start:
1. Install Python 3.11+ from python.org
2. Run `setup_windows.bat`
3. Edit `.env` file with your API keys
4. Run `python main.py`

For detailed instructions, see `WINDOWS_INSTALLATION_GUIDE.md`
EOF

echo "✅ Deployment package created in 'scrapius_deployment' folder"
echo ""
echo "📋 Package contents:"
ls -la scrapius_deployment/
echo ""
echo "🎯 Ready to compress and send to client!"
echo ""

# Optional: Create ZIP file
if command -v zip &> /dev/null; then
    echo "📦 Creating ZIP file..."
    zip -r scrapius_windows_deployment.zip scrapius_deployment/
    echo "✅ Created: scrapius_windows_deployment.zip"
fi 