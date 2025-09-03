# 🐧 Scrapius Linux Deployment Guide

Quick setup guide for deploying Scrapius on Linux servers (Ubuntu/Debian).

## 🚀 Quick Start

### Automated Setup
```bash
git clone https://github.com/0ximgh05t/scrapius.git
cd scrapius
chmod +x setup_linux.sh
./setup_linux.sh
```

### Manual Setup
```bash
# Install dependencies
sudo apt update
sudo apt install -y python3 python3-pip python3-venv google-chrome-stable

# Setup project
git clone https://github.com/0ximgh05t/scrapius.git
cd scrapius
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## ⚙️ Configuration

### 1. Environment Variables
```bash
cp .env.example .env
nano .env
```

**Required settings:**
```env
OPENAI_API_KEY=your_openai_api_key_here
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
ALLOWED_CHAT_IDS=your_chat_id_here

# Linux Chrome (headless)
CHROME_ARGS=--headless,--no-sandbox,--disable-dev-shm-usage,--disable-gpu
CHROME_USER_DATA_DIR=/home/$USER/.config/google-chrome
```

### 2. Facebook Authentication

**Option A: Copy Existing Cookies**
```bash
# From your local machine
scp fb_cookies.json user@server:/path/to/scrapius/
```

**Option B: Import via Telegram**
1. Start bot: `python main.py`
2. Use `/login` → "Import Cookies"
3. Paste cookies from browser extension

## 🔧 Running the Bot

### Development
```bash
source venv/bin/activate
python main.py
```

### Production (systemd service)
```bash
sudo nano /etc/systemd/system/scrapius.service
```

```ini
[Unit]
Description=Scrapius Facebook Scraper Bot
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/scrapius
Environment=PATH=/path/to/scrapius/venv/bin
ExecStart=/path/to/scrapius/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable scrapius
sudo systemctl start scrapius
sudo systemctl status scrapius
```

## 🐳 Docker Deployment

```dockerfile
FROM python:3.11-slim

# Install Chrome
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["python", "main.py"]
```

## 🔍 Troubleshooting

### Chrome Issues
```bash
# Check Chrome installation
google-chrome --version

# Test headless mode
google-chrome --headless --no-sandbox --dump-dom https://www.google.com
```

### Permission Issues
```bash
# Fix Chrome permissions
sudo chown -R $USER:$USER ~/.config/google-chrome
```

### Memory Issues
```bash
# Add swap space
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

## 📊 Monitoring

### Logs
```bash
# View bot logs
tail -f scrapius.log

# System service logs
sudo journalctl -u scrapius -f
```

### Process Monitoring
```bash
# Check if bot is running
ps aux | grep python | grep main.py

# Monitor resource usage
htop
```

## 🔒 Security

### Firewall
```bash
# Only allow SSH and necessary ports
sudo ufw enable
sudo ufw allow ssh
```

### File Permissions
```bash
# Secure sensitive files
chmod 600 .env fb_cookies.json
```

## 🚀 Performance Tips

- **Use SSD storage** for better database performance
- **Allocate 2GB+ RAM** for Chrome processes
- **Monitor CPU usage** during scraping
- **Set appropriate working hours** to reduce load

---

**The bot runs completely headless on Linux servers - no GUI required!** 🎯
