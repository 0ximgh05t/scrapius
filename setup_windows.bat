@echo off
echo 🪟 SCRAPIUS - Windows Setup Script
echo ================================

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found! Please install Python 3.11+ first.
    echo Download from: https://www.python.org/downloads/windows/
    pause
    exit /b 1
)

echo ✅ Python found
python --version

REM Create virtual environment
echo.
echo 📦 Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ❌ Failed to create virtual environment
    pause
    exit /b 1
)

REM Activate virtual environment
echo ✅ Activating virtual environment...
call venv\Scripts\activate

REM Upgrade pip
echo.
echo 📦 Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements
echo.
echo 📦 Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ Failed to install dependencies
    pause
    exit /b 1
)

REM Create .env file if it doesn't exist
if not exist .env (
    echo.
    echo 📝 Creating .env file...
    echo # OpenAI Configuration > .env
    echo OPENAI_API_KEY=your_openai_api_key_here >> .env
    echo. >> .env
    echo # Telegram Bot Configuration >> .env
    echo TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here >> .env
    echo ALLOWED_CHAT_IDS=your_chat_id_here >> .env
    echo. >> .env
    echo # Chrome Configuration ^(Windows paths^) >> .env
    echo CHROME_USER_DATA_DIR=C:\Users\%%USERNAME%%\AppData\Local\Google\Chrome\User Data >> .env
    echo CHROME_PROFILE_DIR=Default >> .env
    echo. >> .env
    echo # Bot Settings >> .env
    echo BOT_PROMPT_SYSTEM=You are a helpful assistant that filters Facebook posts. >> .env
    echo BOT_PROMPT_USER=Send only posts where people are looking for marketing services >> .env
    echo BOT_POLL_SECONDS=600 >> .env
    echo. >> .env
    echo ✅ Created .env file - please edit it with your API keys
)

REM Test installation
echo.
echo 🧪 Testing installation...
python -c "import selenium, requests, openai; print('✅ All packages imported successfully!')"
if errorlevel 1 (
    echo ❌ Package import test failed
    pause
    exit /b 1
)

echo.
echo 🎉 Setup completed successfully!
echo.
echo Next steps:
echo 1. Edit .env file with your API keys: notepad .env
echo 2. Run the bot: python main.py
echo 3. Use Telegram commands to configure
echo.
echo For detailed instructions, see: WINDOWS_INSTALLATION_GUIDE.md
echo.
pause 