import json
import os
from typing import List, Dict
from selenium.webdriver.remote.webdriver import WebDriver


_ALLOWED_COOKIE_KEYS = {"name", "value", "domain", "path", "expiry", "secure", "httpOnly"}


def _sanitize_cookie(cookie: Dict) -> Dict:
    clean = {k: cookie[k] for k in _ALLOWED_COOKIE_KEYS if k in cookie}
    # Ensure expiry is int if present
    if "expiry" in clean:
        try:
            clean["expiry"] = int(clean["expiry"])
        except Exception:
            clean.pop("expiry", None)
    if "path" not in clean:
        clean["path"] = "/"
    return clean


def save_cookies(driver: WebDriver, file_path: str) -> None:
    try:
        cookies = driver.get_cookies()
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f)
    except Exception:
        pass


def load_cookies(driver: WebDriver, file_path: str, target_url: str = None) -> bool:
    """
    Load cookies for Facebook session.
    
    Args:
        driver: WebDriver instance
        file_path: Path to cookies file
        target_url: Target URL to navigate to (if None, goes to facebook.com)
    
    Returns:
        True if cookies loaded successfully
    """
    try:
        if not os.path.exists(file_path):
            return False
        with open(file_path, "r", encoding="utf-8") as f:
            cookies: List[Dict] = json.load(f)
        
        # Navigate to Facebook domain first to set cookies
        driver.get("https://www.facebook.com/")
        
        for c in cookies:
            try:
                driver.add_cookie(_sanitize_cookie(c))
            except Exception:
                continue
        
        # Navigate to target URL or refresh current page
        if target_url:
            driver.get(target_url)
        else:
            driver.refresh()
        
        # Add delay to let session stabilize and avoid bot detection
        import time
        time.sleep(3)
            
        return True
    except Exception:
        return False 