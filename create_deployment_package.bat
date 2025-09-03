@echo off
echo 🚀 Creating Scrapius Windows Deployment Package
echo ===============================================

REM Create deployment directory
if exist scrapius_deployment rmdir /s /q scrapius_deployment
mkdir scrapius_deployment

echo 📦 Copying essential files...

REM Copy main application files
copy main.py scrapius_deployment\
copy config.py scrapius_deployment\
copy requirements.txt scrapius_deployment\
copy .gitignore scrapius_deployment\
copy insights.db scrapius_deployment\

REM Copy directories
echo 📁 Copying directories...
xcopy /E /I ai scrapius_deployment\ai
xcopy /E /I bot scrapius_deployment\bot
xcopy /E /I database scrapius_deployment\database
xcopy /E /I notifier scrapius_deployment\notifier
xcopy /E /I scraper scrapius_deployment\scraper

REM Copy Windows setup files
copy setup_windows.bat scrapius_deployment\
copy README_WINDOWS.md scrapius_deployment\
copy WINDOWS_INSTALLATION_GUIDE.md scrapius_deployment\

REM Create empty .env template
echo # OpenAI Configuration > scrapius_deployment\.env.example
echo OPENAI_API_KEY=your_openai_api_key_here >> scrapius_deployment\.env.example
echo. >> scrapius_deployment\.env.example
echo # Telegram Bot Configuration >> scrapius_deployment\.env.example
echo TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here >> scrapius_deployment\.env.example
echo ALLOWED_CHAT_IDS=your_chat_id_here >> scrapius_deployment\.env.example
echo. >> scrapius_deployment\.env.example
echo # Chrome Configuration (Windows paths) >> scrapius_deployment\.env.example
echo CHROME_USER_DATA_DIR=C:\Users\%%USERNAME%%\AppData\Local\Google\Chrome\User Data >> scrapius_deployment\.env.example
echo CHROME_PROFILE_DIR=Default >> scrapius_deployment\.env.example
echo. >> scrapius_deployment\.env.example
echo # Bot Settings >> scrapius_deployment\.env.example
echo BOT_PROMPT_SYSTEM=You are a helpful assistant that filters Facebook posts. >> scrapius_deployment\.env.example
echo BOT_PROMPT_USER=Send only posts where people are looking for marketing services >> scrapius_deployment\.env.example
echo BOT_POLL_SECONDS=600 >> scrapius_deployment\.env.example
echo. >> scrapius_deployment\.env.example
echo # Facebook Credentials (Optional) >> scrapius_deployment\.env.example
echo FB_USER=your_facebook_email@example.com >> scrapius_deployment\.env.example
echo FB_PASS=your_facebook_password >> scrapius_deployment\.env.example

REM Create deployment README
echo 🤖 **Scrapius Facebook Bot - Ready for Windows Deployment** > scrapius_deployment\README.md
echo. >> scrapius_deployment\README.md
echo ## Quick Start: >> scrapius_deployment\README.md
echo 1. Install Python 3.11+ from python.org >> scrapius_deployment\README.md
echo 2. Run `setup_windows.bat` >> scrapius_deployment\README.md
echo 3. Edit `.env` file with your API keys >> scrapius_deployment\README.md
echo 4. Run `python main.py` >> scrapius_deployment\README.md
echo. >> scrapius_deployment\README.md
echo For detailed instructions, see `WINDOWS_INSTALLATION_GUIDE.md` >> scrapius_deployment\README.md

echo ✅ Deployment package created in 'scrapius_deployment' folder
echo.
echo 📋 Package contents:
dir /b scrapius_deployment
echo.
echo 🎯 Ready to compress and send to client!
echo.
pause 