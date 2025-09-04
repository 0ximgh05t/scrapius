import os
from dotenv import load_dotenv
import getpass
import logging
from typing import List, Tuple
import subprocess
import shutil
import stat
from pathlib import Path
import platform

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Removed get_google_api_key - Gemini AI is no longer used

def get_facebook_credentials() -> tuple[str, str]:
    """
    Securely gets Facebook username and password from environment variables or via command line prompt.
    Prioritizes environment variables (FB_USER, FB_PASS) for non-interactive use.
    If not found in env, prompts the user securely.
    """
    fb_user = os.getenv("FB_USER")
    fb_pass = os.getenv("FB_PASS")

    if fb_user and fb_pass:
        logging.info("Loading Facebook credentials from environment variables.")
        return fb_user, fb_pass
    else:
        logging.info("Facebook credentials not found in environment variables. Prompting user.")
        try:
            username = input("Enter Facebook Email/Username: ")
            password = getpass.getpass("Enter Facebook Password: ")
            if not username or not password:
                raise ValueError("Username or password cannot be empty.")
            return username, password
        except Exception as e:
            logging.error(f"Error getting Facebook credentials: {e}")
            raise ValueError("Failed to get Facebook credentials.") from e


def get_login_timeouts() -> tuple[int, int, int]:
    """Returns (element_wait_secs, post_login_wait_secs, manual_login_grace_secs)."""
    try:
        element_wait = int(os.getenv("FB_ELEMENT_WAIT_SECS", "30"))
    except Exception:
        element_wait = 30
    try:
        post_login_wait = int(os.getenv("FB_POST_LOGIN_WAIT_SECS", "60"))
    except Exception:
        post_login_wait = 60
    try:
        manual_grace = int(os.getenv("FB_MANUAL_LOGIN_GRACE_SECS", "0"))
    except Exception:
        manual_grace = 0
    return element_wait, post_login_wait, manual_grace


def get_telegram_settings() -> Tuple[str | None, List[str]]:
    """Returns (bot_token, allowed_chat_ids) from env; returns (None, []) if not configured."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_ids_raw = os.getenv("ALLOWED_CHAT_IDS", "")
    chat_ids = [cid.strip() for cid in chat_ids_raw.split(',') if cid.strip()]
    return token, chat_ids


def get_telegram_keywords() -> List[str]:
    """Returns lowercased keywords parsed from TELEGRAM_KEYWORDS (comma-separated)."""
    raw = os.getenv("TELEGRAM_KEYWORDS", "")
    return [kw.strip().lower() for kw in raw.split(',') if kw.strip()]


def get_chrome_profile_settings() -> Tuple[str | None, str | None]:
    """Returns (user_data_dir, profile_dir) from env if provided.
    CHROME_USER_DATA_DIR points to a Chrome user data directory; CHROME_PROFILE_DIR is the profile name (e.g., 'Default').
    """
    udd = os.getenv("CHROME_USER_DATA_DIR")
    pd = os.getenv("CHROME_PROFILE_DIR")
    return udd, pd


def get_openai_settings() -> Tuple[bool, str | None]:
    key = os.getenv("OPENAI_API_KEY")
    return (bool(key), key)


def get_bot_runner_settings() -> Tuple[str, str, list[str], int]:
    system_prompt = os.getenv("BOT_PROMPT_SYSTEM", "You are a helpful assistant that filters Facebook posts.")
    user_prompt = os.getenv("BOT_PROMPT_USER", "Decide if this post is worth notifying about and provide a one-paragraph summary.")
    group_urls = [u.strip() for u in os.getenv("BOT_GROUP_URLS", "").split(',') if u.strip()]
    # PRODUCTION RELIABILITY: Much less aggressive polling (10 minutes default instead of 2)
    poll_seconds = int(os.getenv("BOT_POLL_SECONDS", "600"))  # 10 minutes for long-term stability
    return system_prompt, user_prompt, group_urls, poll_seconds


def get_hourly_limit_defaults() -> int:
    """Returns hourly_limit (runs per hour). PRODUCTION: Conservative default for reliability."""
    # PRODUCTION RELIABILITY: 6 times per hour = every 10 minutes (was too aggressive before)
    return int(os.getenv("BOT_HOURLY_LIMIT", "6"))

def get_reliability_settings(conn=None) -> dict:
    """
    Production-grade reliability settings for long-term operation.
    Reads from database if connection provided, otherwise from env vars.
    """
    if conn:
        try:
            from database.crud import botsettings_get
            group_delay = int(botsettings_get(conn, 'group_delay', '30'))
            post_delay = float(botsettings_get(conn, 'post_delay', '1.0'))
            max_posts = int(botsettings_get(conn, 'max_posts_per_group', '10'))
        except:
            # Fallback to env vars if database read fails
            group_delay = int(os.getenv("BOT_GROUP_DELAY", "30"))
            post_delay = float(os.getenv("BOT_POST_DELAY", "1.0"))
            max_posts = int(os.getenv("BOT_MAX_POSTS", "10"))
    else:
        group_delay = int(os.getenv("BOT_GROUP_DELAY", "30"))
        post_delay = float(os.getenv("BOT_POST_DELAY", "1.0"))
        max_posts = int(os.getenv("BOT_MAX_POSTS", "10"))
    
    return {
        # Delays between operations (seconds)
        'group_delay': group_delay,
        'scroll_delay': float(os.getenv("BOT_SCROLL_DELAY", "3.0")),  # 3s between scrolls
        'post_processing_delay': post_delay,
        
        # Retry settings
        'max_retries': int(os.getenv("BOT_MAX_RETRIES", "5")),
        'retry_delay_base': int(os.getenv("BOT_RETRY_DELAY", "2")),
        'retry_delay_max': int(os.getenv("BOT_RETRY_MAX_DELAY", "30")),
        
        # Error recovery
        'stale_element_max_retries': int(os.getenv("BOT_STALE_RETRIES", "3")),
        'session_check_interval': int(os.getenv("BOT_SESSION_CHECK", "300")),  # 5 minutes
        
        # Conservative limits
        'max_posts_per_group': max_posts,
        'page_load_timeout': int(os.getenv("BOT_PAGE_TIMEOUT", "45")),  # Increased timeout
    }

def get_working_hours_settings(conn=None) -> dict:
    """
    Working hours configuration for bot operation scheduling.
    All times are in GMT+3 timezone.
    Reads from database if connection provided, otherwise from env vars.
    """
    if conn:
        try:
            from database.crud import botsettings_get
            enabled = botsettings_get(conn, 'working_hours_enabled', 'false').lower() == 'true'
            start_hour = int(botsettings_get(conn, 'working_hours_start', '8'))
            end_hour = int(botsettings_get(conn, 'working_hours_end', '16'))
        except:
            # Fallback to env vars if database read fails
            enabled = os.getenv("BOT_WORKING_HOURS_ENABLED", "false").lower() == "true"
            start_hour = int(os.getenv("BOT_WORKING_START", "8"))
            end_hour = int(os.getenv("BOT_WORKING_END", "16"))
    else:
        enabled = os.getenv("BOT_WORKING_HOURS_ENABLED", "false").lower() == "true"
        start_hour = int(os.getenv("BOT_WORKING_START", "8"))
        end_hour = int(os.getenv("BOT_WORKING_END", "16"))
    
    return {
        # Working hours enabled/disabled
        'enabled': enabled,
        
        # Working hours (24-hour format, GMT+3)
        'start_hour': start_hour,
        'end_hour': end_hour,
        
        # Timezone offset from UTC
        'timezone_offset': int(os.getenv("BOT_TIMEZONE_OFFSET", "3")),  # GMT+3
        
        # Working days (0=Monday, 6=Sunday)
        'working_days': [int(d.strip()) for d in os.getenv("BOT_WORKING_DAYS", "0,1,2,3,4").split(',') if d.strip()],  # Mon-Fri default
    }

def is_within_working_hours(conn=None) -> bool:
    """
    Check if current time is within configured working hours (GMT+3).
    Returns True if working hours are disabled or if current time is within working hours.
    """
    from datetime import datetime, timezone, timedelta
    
    settings = get_working_hours_settings(conn)
    
    # If working hours are disabled, always return True
    if not settings['enabled']:
        return True
    
    # Get current time in the configured timezone
    tz_offset = timedelta(hours=settings['timezone_offset'])
    local_tz = timezone(tz_offset)
    now_local = datetime.now(local_tz)
    
    # Check if current day is a working day
    current_weekday = now_local.weekday()  # 0=Monday, 6=Sunday
    if current_weekday not in settings['working_days']:
        return False
    
    # Check if current hour is within working hours
    current_hour = now_local.hour
    return settings['start_hour'] <= current_hour < settings['end_hour']

def get_next_working_time(conn=None) -> str:
    """
    Get human-readable description of when bot will next be active.
    """
    from datetime import datetime, timezone, timedelta
    
    settings = get_working_hours_settings(conn)
    
    if not settings['enabled']:
        return "Working hours disabled - bot runs 24/7"
    
    tz_offset = timedelta(hours=settings['timezone_offset'])
    local_tz = timezone(tz_offset)
    now_local = datetime.now(local_tz)
    
    # If currently within working hours
    if is_within_working_hours(conn):
        end_time = now_local.replace(hour=settings['end_hour'], minute=0, second=0, microsecond=0)
        return f"Active until {end_time.strftime('%H:%M')} GMT+{settings['timezone_offset']}"
    
    # Find next working period
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    working_days_names = [days[d] for d in settings['working_days']]
    
    return f"Next active: {working_days_names[0]}-{working_days_names[-1]} {settings['start_hour']:02d}:00-{settings['end_hour']:02d}:00 GMT+{settings['timezone_offset']}"


def get_cookie_store_path() -> str:
    path = os.getenv("COOKIE_STORE_PATH")
    if path:
        return path
    return os.path.abspath(os.path.join(os.path.dirname(__file__), 'fb_cookies.json'))


def get_chrome_executable_path():
    """
    Get Chrome executable path across different operating systems.
    """
    system = platform.system().lower()
    
    if system == "darwin":  # macOS
        chrome_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium"
        ]
    elif system == "windows":  # Windows
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
            r"C:\Program Files\Chromium\Application\chromium.exe"
        ]
    else:  # Linux
        chrome_paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable", 
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
            "/snap/bin/chromium"
        ]
    
    for path in chrome_paths:
        if os.path.exists(path):
            logging.info(f"🔍 Found Chrome at: {path}")
            return path
    
    # Try to find in PATH
    for name in ["google-chrome", "chrome", "chromium", "chromium-browser"]:
        path = shutil.which(name)
        if path:
            logging.info(f"🔍 Found Chrome in PATH: {path}")
            return path
    
    raise RuntimeError("Chrome/Chromium not found on system")

def get_reliable_chromedriver_path() -> str:
    """
    Get a reliable ChromeDriver path that works across all platforms.
    """
    system = platform.system().lower()
    
    try:
        # Try system PATH first (most reliable)
        chromedriver_path = shutil.which('chromedriver')
        if chromedriver_path:
            logging.info(f"🔍 Found ChromeDriver in PATH: {chromedriver_path}")
            return chromedriver_path
        
        # Platform-specific locations
        if system == "darwin":  # macOS
            homebrew_chromedriver = "/opt/homebrew/bin/chromedriver"
            if os.path.exists(homebrew_chromedriver):
                logging.info(f"🍺 Using Homebrew ChromeDriver: {homebrew_chromedriver}")
                return homebrew_chromedriver
        
        # Fallback: Use webdriver-manager but fix permissions
        from webdriver_manager.chrome import ChromeDriverManager
        driver_path = ChromeDriverManager().install()
        
        # Fix platform-specific security issues
        if os.path.exists(driver_path):
            if system == "darwin":  # macOS security fixes
                # Remove ALL quarantine attributes
                quarantine_attrs = ['com.apple.quarantine', 'com.apple.provenance', 'com.apple.metadata:kMDItemWhereFroms']
                for attr in quarantine_attrs:
                    try:
                        subprocess.run(['xattr', '-d', attr, driver_path], 
                                     capture_output=True, check=False)
                    except:
                        pass
            
            # Set executable permissions (all platforms)
            try:
                os.chmod(driver_path, 0o755)
                logging.info("🔧 Set executable permissions on ChromeDriver")
            except Exception as e:
                logging.warning(f"Could not set permissions: {e}")
            
            # Test if ChromeDriver can execute
            try:
                result = subprocess.run([driver_path, '--version'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    logging.info("✅ ChromeDriver test successful")
                    return driver_path
                else:
                    logging.error(f"ChromeDriver test failed: {result.stderr}")
            except Exception as e:
                logging.error(f"ChromeDriver test error: {e}")
        
        raise RuntimeError("All ChromeDriver options failed")
        
    except Exception as e:
        logging.error(f"Failed to get reliable ChromeDriver: {e}")
        raise RuntimeError("Could not find or fix ChromeDriver installation")

def create_chrome_with_remote_debugging(headless: bool = True, debug_port: int = 9222):
    """
    BULLETPROOF: Create Chrome with remote debugging - works on ALL platforms.
    """
    import subprocess
    import time
    import requests
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    
    try:
        # Kill any existing Chrome processes on the debug port
        system = platform.system().lower()
        try:
            if system == "windows":
                subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], 
                             capture_output=True, check=False)
            else:
                subprocess.run(['pkill', '-f', f'remote-debugging-port={debug_port}'], 
                             capture_output=True, check=False)
            time.sleep(2)
        except:
            pass
        
        # Get Chrome executable and profile settings
        chrome_executable = get_chrome_executable_path()
        user_data_dir, profile_dir = get_chrome_profile_settings()
        
        # Build Chrome command
        chrome_cmd = [
            chrome_executable,
            f'--remote-debugging-port={debug_port}',
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-default-apps',
            '--disable-popup-blocking',
            '--disable-translate',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-features=TranslateUI,VizDisplayCompositor',
            '--disable-web-security',
            '--disable-sync'
        ]
        
        if user_data_dir:
            chrome_cmd.append(f'--user-data-dir={user_data_dir}')
        if profile_dir:
            chrome_cmd.append(f'--profile-directory={profile_dir}')
        
        if headless:
            chrome_cmd.extend([
                '--headless=new',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--window-size=1920,1080',
                '--disable-images'
            ])
        
        # Start Chrome with remote debugging
        logging.info(f"🚀 Starting Chrome with remote debugging on port {debug_port}")
        
        # Platform-specific process creation
        if system == "windows":
            chrome_process = subprocess.Popen(chrome_cmd, 
                                            stdout=subprocess.DEVNULL, 
                                            stderr=subprocess.DEVNULL,
                                            creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            chrome_process = subprocess.Popen(chrome_cmd, 
                                            stdout=subprocess.DEVNULL, 
                                            stderr=subprocess.DEVNULL)
        
        # Wait for Chrome to start
        for i in range(30):  # 30 second timeout
            try:
                response = requests.get(f'http://localhost:{debug_port}/json/version', timeout=1)
                if response.status_code == 200:
                    logging.info("✅ Chrome remote debugging ready")
                    break
            except:
                time.sleep(1)
        else:
            chrome_process.terminate()
            raise RuntimeError("Chrome remote debugging failed to start")
        
        # Connect Selenium to the remote Chrome
        options = webdriver.ChromeOptions()
        options.add_experimental_option("debuggerAddress", f"localhost:{debug_port}")
        
        # Try to get ChromeDriver
        try:
            driver_path = get_reliable_chromedriver_path()
            service = Service(executable_path=driver_path)
            driver = webdriver.Chrome(service=service, options=options)
        except:
            # If ChromeDriver fails, try without explicit service
            logging.warning("ChromeDriver not available, trying system default")
            driver = webdriver.Chrome(options=options)
        
        # Store Chrome process reference for cleanup
        driver._chrome_process = chrome_process
        driver._debug_port = debug_port
        
        # Add cleanup method
        original_quit = driver.quit
        def enhanced_quit():
            try:
                original_quit()
            except:
                pass
            try:
                chrome_process.terminate()
                chrome_process.wait(timeout=5)
            except:
                try:
                    chrome_process.kill()
                except:
                    pass
        driver.quit = enhanced_quit
        
        logging.info("✅ Remote debugging WebDriver created successfully")
        return driver
        
    except Exception as e:
        logging.error(f"Failed to create remote debugging WebDriver: {e}")
        raise RuntimeError(f"Could not initialize remote debugging WebDriver: {e}")

def setup_chrome_options(headless: bool = True, user_data_dir: str = None, profile_dir: str = None):
    """
    Create robust Chrome options that work reliably across all environments.
    """
    from selenium import webdriver
    
    options = webdriver.ChromeOptions()
    
    # Profile settings
    if user_data_dir:
        options.add_argument(f"--user-data-dir={user_data_dir}")
    if profile_dir:
        options.add_argument(f"--profile-directory={profile_dir}")
    
    # Robust headless configuration
    if headless:
        options.add_argument('--headless=new')  # Use new headless mode
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-web-security')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-plugins')
        options.add_argument('--disable-images')
        options.add_argument('--disable-features=VizDisplayCompositor')
        options.add_argument('--disable-background-timer-throttling')
        options.add_argument('--disable-backgrounding-occluded-windows')
        options.add_argument('--disable-renderer-backgrounding')
    
    # Essential stability options
    options.add_argument('--no-first-run')
    options.add_argument('--no-default-browser-check')
    options.add_argument('--disable-default-apps')
    options.add_argument('--disable-background-networking')
    options.add_argument('--disable-sync')
    options.add_argument('--metrics-recording-only')
    options.add_argument('--no-report-upload')
    
    # Enhanced browser fingerprinting to match your local browser
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.7339.80 Safari/537.36")
    
    # Additional headers to match your local browser
    options.add_argument('--accept-language=en-US,en;q=0.9')
    options.add_argument('--accept-encoding=gzip, deflate, br')
    options.add_argument('--accept=text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8')
    
    # Timezone and locale spoofing (set to your local timezone)
    options.add_argument('--lang=en-US')
    
    # Disable WebRTC to prevent IP leaks
    options.add_experimental_option("prefs", {
        "webrtc.ip_handling_policy": "disable_non_proxied_udp",
        "webrtc.multiple_routes_enabled": False,
        "webrtc.nonproxied_udp_enabled": False
    })
    

    
    return options

def create_reliable_webdriver(headless: bool = True):
    """
    Create a WebDriver instance that's guaranteed to work reliably.
    Uses multiple fallback strategies for maximum reliability.
    """
    # Strategy 1: Try remote debugging (most reliable on macOS)
    try:
        return create_chrome_with_remote_debugging(headless=headless)
    except Exception as e:
        logging.warning(f"Remote debugging failed: {e}")
    
    # Strategy 2: Try traditional ChromeDriver
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        
        # Get reliable ChromeDriver path
        driver_path = get_reliable_chromedriver_path()
        logging.info(f"🚀 Using ChromeDriver: {driver_path}")
        
        # Get Chrome profile settings
        user_data_dir, profile_dir = get_chrome_profile_settings()
        
        # Setup robust options
        options = setup_chrome_options(headless, user_data_dir, profile_dir)
        
        # Create service with explicit path
        service = Service(executable_path=driver_path)
        
        # Create WebDriver
        driver = webdriver.Chrome(service=service, options=options)
        
        logging.info("✅ Traditional WebDriver created successfully")
        return driver
        
    except Exception as e:
        logging.error(f"Traditional WebDriver failed: {e}")
    
    # Strategy 3: Last resort - system ChromeDriver
    try:
        from selenium import webdriver
        user_data_dir, profile_dir = get_chrome_profile_settings()
        options = setup_chrome_options(headless, user_data_dir, profile_dir)
        
        driver = webdriver.Chrome(options=options)
        logging.info("✅ System ChromeDriver created successfully")
        return driver
        
    except Exception as e:
        logging.error(f"All WebDriver strategies failed: {e}")
        raise RuntimeError(f"Could not initialize any WebDriver: {e}")

