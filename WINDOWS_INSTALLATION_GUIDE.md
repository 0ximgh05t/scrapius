# 🪟 **SCRAPIUS - WINDOWS INSTALLATION GUIDE**

## **📋 PREREQUISITES**

### **1. Install Python 3.11+ on Windows**
```powershell
# Download Python from: https://www.python.org/downloads/windows/
# ✅ IMPORTANT: Check "Add Python to PATH" during installation
# ✅ IMPORTANT: Choose "Install for all users"

# Verify installation
python --version
# Should show: Python 3.11.x or higher
```

### **2. Install Google Chrome**
```powershell
# Download from: https://www.google.com/chrome/
# Install normally - required for Selenium automation
```

### **3. Install Git (Optional but Recommended)**
```powershell
# Download from: https://git-scm.com/download/win
# Or use GitHub Desktop: https://desktop.github.com/
```

## **🚀 INSTALLATION STEPS**

### **Step 1: Download Project**

**Option A: Using Git**
```powershell
# Open Command Prompt or PowerShell as Administrator
cd C:\
git clone https://github.com/your-repo/scrapius.git
cd scrapius
```

**Option B: Manual Download**
```powershell
# 1. Download ZIP from GitHub
# 2. Extract to C:\scrapius\
# 3. Open Command Prompt as Administrator
cd C:\scrapius
```

### **Step 2: Create Virtual Environment**
```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate

# You should see (venv) in your prompt
```

### **Step 3: Install Dependencies**
```powershell
# Upgrade pip first
python -m pip install --upgrade pip

# Install all requirements
pip install -r requirements.txt

# Verify installation
pip list
```

### **Step 4: Configure Environment**
```powershell
# Copy example environment file
copy .env.example .env

# Edit .env file with Notepad
notepad .env
```

**Add these settings to `.env`:**
```env
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
```

### **Step 5: Test Installation**
```powershell
# Test basic functionality
python -c "import selenium, requests, openai; print('✅ All packages imported successfully!')"

# Test bot startup
python main.py
```

## **🔧 WINDOWS-SPECIFIC CONFIGURATION**

### **Chrome Profile Setup**
```powershell
# Find your Chrome profile directory
echo %LOCALAPPDATA%\Google\Chrome\User Data

# Common paths:
# C:\Users\[USERNAME]\AppData\Local\Google\Chrome\User Data\Default
# C:\Users\[USERNAME]\AppData\Local\Google\Chrome\User Data\Profile 1
```

### **Windows Firewall**
```powershell
# Allow Python through Windows Firewall
# Go to: Windows Security > Firewall & network protection > Allow an app through firewall
# Add: python.exe from your venv\Scripts\ folder
```

### **Windows Service (Optional)**
```powershell
# To run as Windows Service, install:
pip install pywin32

# Then use Windows Task Scheduler to run at startup
```

## **🚀 RUNNING THE BOT**

### **Manual Start**
```powershell
# Navigate to project directory
cd C:\scrapius

# Activate virtual environment
venv\Scripts\activate

# Run the bot
python main.py
```

### **Auto-Start with Windows**

**Option 1: Task Scheduler**
1. Open Task Scheduler
2. Create Basic Task
3. Name: "Scrapius Bot"
4. Trigger: "When the computer starts"
5. Action: "Start a program"
6. Program: `C:\scrapius\venv\Scripts\python.exe`
7. Arguments: `main.py`
8. Start in: `C:\scrapius`

**Option 2: Startup Folder**
```powershell
# Create batch file: start_scrapius.bat
@echo off
cd /d C:\scrapius
call venv\Scripts\activate
python main.py
pause

# Copy to startup folder:
# Win+R, type: shell:startup
# Paste the batch file there
```

## **🔍 TROUBLESHOOTING**

### **Common Issues**

**1. Python not found**
```powershell
# Add Python to PATH manually
# System Properties > Environment Variables > PATH
# Add: C:\Users\[USERNAME]\AppData\Local\Programs\Python\Python311\
# Add: C:\Users\[USERNAME]\AppData\Local\Programs\Python\Python311\Scripts\
```

**2. Chrome not found**
```powershell
# Install Chrome from: https://www.google.com/chrome/
# Or update CHROME_USER_DATA_DIR in .env
```

**3. Permission errors**
```powershell
# Run Command Prompt as Administrator
# Right-click > "Run as administrator"
```

**4. ChromeDriver issues**
```powershell
# webdriver-manager will auto-download ChromeDriver
# If issues persist, manually download from:
# https://chromedriver.chromium.org/
```

**5. Virtual environment issues**
```powershell
# Delete and recreate venv
rmdir /s venv
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## **📱 TELEGRAM COMMANDS**

Once running, use these commands in Telegram:

```
/config - View all settings
/sethours 8-16 - Set working hours
/setlimit 4 - Set scraping frequency
/settiming normal - Set timing presets
/login - Facebook login setup
```

## **🔒 SECURITY NOTES**

1. **Keep `.env` file secure** - contains API keys
2. **Use strong Facebook password**
3. **Enable 2FA on Facebook** (may require app passwords)
4. **Run with limited user account** (not Administrator)
5. **Keep Windows and Chrome updated**

## **📊 MONITORING**

### **Check if running**
```powershell
# Check if Python process is running
tasklist | findstr python

# Check log files
type scrapius.log
```

### **Performance monitoring**
```powershell
# Monitor CPU/Memory usage
# Task Manager > Details > python.exe
```

## **🆘 SUPPORT**

If you encounter issues:

1. **Check logs**: Look at `scrapius.log` file
2. **Test components**: Run individual test commands
3. **Restart services**: Restart bot and Chrome
4. **Update dependencies**: `pip install -r requirements.txt --upgrade`

## **✅ FINAL CHECKLIST**

- [ ] Python 3.11+ installed with PATH
- [ ] Google Chrome installed
- [ ] Project downloaded to `C:\scrapius`
- [ ] Virtual environment created and activated
- [ ] All dependencies installed (`pip list` shows packages)
- [ ] `.env` file configured with API keys
- [ ] Bot starts without errors (`python main.py`)
- [ ] Telegram commands work (`/config`)
- [ ] Facebook login successful
- [ ] Auto-start configured (optional)

**🎉 Your Scrapius bot is now ready for 24/7 operation on Windows!** 