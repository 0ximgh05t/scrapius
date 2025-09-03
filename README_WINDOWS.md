# 🤖 Scrapius Facebook Bot - Windows Installation

## **⚡ QUICK START (5 Minutes)**

### **1. Prerequisites**
- Install **Python 3.11+** from [python.org](https://www.python.org/downloads/windows/)
  - ✅ **IMPORTANT**: Check "Add Python to PATH" during installation
- Install **Google Chrome** from [google.com/chrome](https://www.google.com/chrome/)

### **2. Automated Setup**
```powershell
# 1. Download project files to C:\scrapius\
# 2. Open Command Prompt as Administrator
# 3. Run setup script:
cd C:\scrapius
setup_windows.bat
```

### **3. Configure API Keys**
```powershell
# Edit configuration file
notepad .env

# Add your keys:
OPENAI_API_KEY=sk-your-key-here
TELEGRAM_BOT_TOKEN=your-bot-token
ALLOWED_CHAT_IDS=your-chat-id
```

### **4. Run the Bot**
```powershell
# Activate environment and start
venv\Scripts\activate
python main.py
```

## **📱 Telegram Commands**

Once running, control via Telegram:

```
/config - View all settings
/sethours 8-16 - Set working hours (8 AM - 4 PM)
/setlimit 4 - Scrape every 15 minutes
/settiming normal - Balanced speed
/login - Facebook login setup
```

## **🔧 Auto-Start with Windows**

**Option 1: Task Scheduler (Recommended)**
1. Open Task Scheduler
2. Create Basic Task → "Scrapius Bot"
3. Trigger: "When computer starts"
4. Program: `C:\scrapius\venv\Scripts\python.exe`
5. Arguments: `main.py`
6. Start in: `C:\scrapius`

**Option 2: Startup Folder**
1. Create `start_bot.bat`:
```batch
@echo off
cd /d C:\scrapius
call venv\Scripts\activate
python main.py
```
2. Copy to startup folder (Win+R → `shell:startup`)

## **🆘 Troubleshooting**

**Bot not starting?**
```powershell
# Check Python installation
python --version

# Reinstall dependencies
pip install -r requirements.txt --upgrade

# Check logs
type scrapius.log
```

**Chrome issues?**
- Ensure Chrome is installed and updated
- Check Windows Firewall settings
- Run Command Prompt as Administrator

## **📊 Monitoring**

**Check if running:**
```powershell
tasklist | findstr python
```

**View logs:**
```powershell
type scrapius.log
```

## **🔒 Security**

- Keep `.env` file secure (contains API keys)
- Use strong Facebook password
- Enable Windows Firewall
- Run with limited user account (not Administrator)

## **📞 Support**

For detailed instructions: `WINDOWS_INSTALLATION_GUIDE.md`

**🎉 Your bot will now monitor Facebook groups 24/7 and send relevant posts to Telegram!** 