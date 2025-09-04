import uuid
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Iterator
import logging
from datetime import datetime
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, WebDriverException, ElementClickInterceptedException
import time
import re
import json
from urllib.parse import urlparse, parse_qs
import concurrent.futures
import dateparser
# Timestamp parsing abandoned - timestamps set to None
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import pyperclip
import hashlib
import os
import subprocess
import threading

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger().setLevel(logging.INFO)

# Global variable to track virtual display process
_xvfb_process = None

def setup_virtual_display():
    """Setup virtual display for clipboard operations in headless mode."""
    global _xvfb_process
    
    # Check if already running
    if _xvfb_process and _xvfb_process.poll() is None:
        logging.debug("Virtual display already running")
        return True
    
    try:
        # Check for Xvfb in common locations (XQuartz on macOS)
        xvfb_paths = ['/opt/X11/bin/Xvfb', '/usr/bin/Xvfb', 'Xvfb']
        xvfb_path = None
        
        for path in xvfb_paths:
            result = subprocess.run(['which', path] if path == 'Xvfb' else ['test', '-f', path], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                xvfb_path = path
                break
        
        if not xvfb_path:
            logging.warning("Xvfb not found. Clipboard operations may not work in headless mode.")
            return False
        
        # Start virtual display
        _xvfb_process = subprocess.Popen([
            xvfb_path, ':99', '-screen', '0', '1920x1080x24', '-ac', '+extension', 'GLX'
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Set DISPLAY environment variable
        os.environ['DISPLAY'] = ':99'
        
        # Give it a moment to start
        time.sleep(2)
        
        logging.info(f"✅ Virtual display started using {xvfb_path}")
        return True
        
    except Exception as e:
        logging.warning(f"Failed to setup virtual display: {e}")
        return False

def cleanup_virtual_display():
    """Cleanup virtual display."""
    global _xvfb_process
    if _xvfb_process:
        try:
            _xvfb_process.terminate()
            _xvfb_process.wait(timeout=5)
            logging.info("✅ Virtual display cleaned up")
        except Exception as e:
            logging.warning(f"Error cleaning up virtual display: {e}")
            try:
                _xvfb_process.kill()
            except:
                pass
        finally:
            _xvfb_process = None

POST_CONTAINER_S = (By.CSS_SELECTOR, 'div.x1yztbdb.x1n2onr6.xh8yej3.x1ja2u2z, div[role="article"]')
POST_PERMALINK_XPATH_S = (By.XPATH, ".//a[contains(@href, '/posts/')] | .//abbr/ancestor::a")
POST_TIMESTAMP_FALLBACK_XPATH_S = (By.XPATH, ".//abbr | .//a/span[@data-lexical-text='true']")
FEED_OR_SCROLLER_S = (By.CSS_SELECTOR, "div[role='feed'], div[data-testid='post_scroller']")
FEED_OR_SCROLLER_XPATH_S = (By.XPATH, "//div[@role='feed'] | //div[@data-testid='post_scroller']")
SEE_MORE_BUTTON_XPATH_S = (By.XPATH, ".//div[@role='button'][contains(., 'See more') or contains(., 'Show more')] | .//a[contains(., 'See more') or contains(., 'Show more')]")

POST_CONTAINER_BS = 'div.x1yztbdb.x1n2onr6.xh8yej3.x1ja2u2z, div[role="article"]'

AUTHOR_PIC_SVG_IMG_BS = 'div:first-child svg image'
AUTHOR_PIC_IMG_BS = 'div:first-child img[alt*="profile picture"], div:first-child img[data-imgperflogname*="profile"]'
SPECIFIC_AUTHOR_PIC_BS = 'div[role="button"] svg image'
AUTHOR_PROFILE_PIC_BS = f'{AUTHOR_PIC_SVG_IMG_BS}, {AUTHOR_PIC_IMG_BS}, {SPECIFIC_AUTHOR_PIC_BS}'

AUTHOR_NAME_PRIMARY_BS = 'h2 strong, h2 a[role="link"] strong, h3 strong, h3 a[role="link"] strong, a[aria-label][href*="/user/"] > strong, a[aria-label][href*="/profile.php"] > strong'
ANON_AUTHOR_NAME_BS = 'h2[id^="«r"] strong object div'
GENERAL_AUTHOR_NAME_BS = 'a[href*="/groups/"][href*="/user/"] span, a[href*="/profile.php"] span, span > strong > a[role="link"]'
AUTHOR_NAME_BS = f'{AUTHOR_NAME_PRIMARY_BS}, {ANON_AUTHOR_NAME_BS}, {GENERAL_AUTHOR_NAME_BS}'

POST_TEXT_CONTAINER_BS = 'div[data-ad-rendering-role="story_message"], div[data-ad-preview="message"], div[data-ad-comet-preview="message"]'
GENERIC_TEXT_DIV_BS = 'div[dir="auto"]:not([class*=" "]):not(:has(button)):not(:has(a[role="button"]))'

POST_IMAGE_BS = 'img.x168nmei, div[data-imgperflogname="MediaGridPhoto"] img, div[style*="background-image"]'

COMMENT_CONTAINER_BS = 'div[aria-label*="Comment by"], ul > li div[role="article"]'

COMMENTER_PIC_SVG_IMG_BS = 'svg image'
COMMENTER_PIC_IMG_BS = 'img[alt*="profile picture"], img[data-imgperflogname*="profile"]'
SPECIFIC_COMMENTER_PIC_BS = 'a[role="link"] svg image'
COMMENTER_PROFILE_PIC_BS = f'{COMMENTER_PIC_SVG_IMG_BS}, {COMMENTER_PIC_IMG_BS}, {SPECIFIC_COMMENTER_PIC_BS}'


COMMENTER_NAME_PRIMARY_BS = 'a[href*="/user/"] span, a[href*="/profile.php"] span, span > a[role="link"] > span > span[dir="auto"]'
GENERAL_COMMENTER_NAME_BS = 'div[role="button"] > strong > span, a[aria-hidden="false"][role="link"]'
COMMENTER_NAME_BS = f'{COMMENTER_NAME_PRIMARY_BS}, {GENERAL_COMMENTER_NAME_BS}'

COMMENT_TEXT_PRIMARY_BS = 'div[data-ad-preview="message"] > span, div[dir="auto"][style="text-align: start;"]'
COMMENT_TEXT_CONTAINER_FALLBACK_BS = '.xmjcpbm.xtq9sad + div, .xv55zj0 + div'
COMMENT_ACTUAL_TEXT_FALLBACK_BS = 'div[dir="auto"], span[dir="auto"]'

COMMENT_ID_LINK_BS = "a[href*='comment_id=']"
COMMENT_TIMESTAMP_ABBR_BS = 'abbr[title]'
COMMENT_TIMESTAMP_LINK_BS = "a[aria-label*='Comment permalink']"

POST_TIMESTAMP_ABBR_BS = 'abbr[title]'
POST_TIMESTAMP_LINK_TEXT_BS = 'a[href*="/posts/"] span[data-lexical-text="true"]'


# PRODUCTION RELIABILITY: Enhanced retry decorator for all critical functions
def production_retry(max_attempts=5):
    """Production-grade retry decorator with exponential backoff."""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=2, min=1, max=30),
        retry=retry_if_exception_type(
            (NoSuchElementException, StaleElementReferenceException, TimeoutException, 
             ElementClickInterceptedException, WebDriverException)
        ),
        reraise=True
    )

def safe_element_operation(operation_func, element, max_retries=3, operation_name="operation"):
    """
    BULLETPROOF: Safely perform operations on potentially stale elements.
    Automatically refetches elements if they become stale.
    """
    for attempt in range(max_retries):
        try:
            return operation_func(element)
        except StaleElementReferenceException:
            if attempt < max_retries - 1:
                logging.warning(f"🔄 Stale element during {operation_name}, attempt {attempt + 1}/{max_retries}")
                time.sleep(0.5 * (attempt + 1))  # Progressive delay
                # Element will be refetched by caller
                continue
            else:
                logging.error(f"❌ {operation_name} failed after {max_retries} attempts due to stale elements")
                raise
        except Exception as e:
            logging.warning(f"⚠️ {operation_name} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise
    return None


@production_retry()
def check_facebook_session(driver: WebDriver, target_url: str = None) -> bool:
    """
    Checks if the current Selenium WebDriver instance is still logged into Facebook.
    If target_url is provided, checks session validity on that page directly.
    """
    logging.info("Checking Facebook session validity...")
    try:
        # If we have a target URL, check session there directly
        if target_url:
            current_url = driver.current_url
            # If we're already on the target page, just check for login indicators
            if target_url in current_url:
                check_url = current_url
            else:
                check_url = target_url
                driver.get(check_url)
        else:
            check_url = "https://www.facebook.com/"
            driver.get(check_url)
        
        # Check for login indicators (logged in = has feed or groups page elements)
        WebDriverWait(driver, 10).until(
            EC.any_of(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='feed']")),
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[aria-label='Home']")),
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-pagelet*='Feed']")),
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='main']"))
            )
        )
        
        # Additional check: make sure we're not on login page
        if "login" in driver.current_url.lower():
            logging.warning("Redirected to login page - session invalid")
            return False
            
        logging.info("✅ Session is valid")
        return True
    except (TimeoutException, NoSuchElementException, WebDriverException) as e:
        logging.warning(f"❌ Session appears invalid: {e}")
        return False

@production_retry()
def login_to_facebook(driver: WebDriver, username: str, password: str) -> bool:
    """
    Automates logging into Facebook using provided credentials.

    Args:
        driver: The Selenium WebDriver instance.
        username: The Facebook username (email or phone).
        password: The Facebook password.

    Returns:
        True if login is successful, False otherwise.
    """
    login_successful = False
    try:
        logging.info("Navigating to Facebook login page.")
        driver.get("https://www.facebook.com/")

        try:
            accept_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-cookiebanner='accept_button']"))
            )
            accept_button.click()
            logging.debug("Accepted cookie consent.")
            time.sleep(2)
        except (NoSuchElementException, TimeoutException):
            logging.debug("No cookie consent dialog found or already accepted.")
            pass

        logging.debug("Attempting to find email/phone field.")
        email_field = WebDriverWait(driver, 20).until(
            EC.visibility_of_element_located((By.ID, "email"))
        )
        logging.debug("Email field found. Entering username.")
        email_field.send_keys(username)

        logging.debug("Attempting to find password field.")
        password_field = WebDriverWait(driver, 20).until(
            EC.visibility_of_element_located((By.ID, "pass"))
        )
        logging.debug("Password field found. Entering password.")
        password_field.send_keys(password)

        logging.debug("Attempting to find login button.")
        login_button = WebDriverWait(driver, 20).until(
             EC.element_to_be_clickable((By.NAME, "login"))
        )
        logging.debug("Login button found. Clicking login.")
        login_button.click()

        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR, "div[role='feed'], a[aria-label='Home'], div[data-pagelet*='Feed']"
                ))
            )
            logging.info("Login successful: Feed element or Home link found.")
            login_successful = True
        except TimeoutException:
            logging.warning("Login appeared to fail or took too long to redirect.")
            
            # Check for specific challenges
            current_url = driver.current_url.lower()
            page_source = driver.page_source.lower()
            
            if "checkpoint" in current_url:
                logging.error("❌ Facebook security checkpoint detected - requires manual intervention")
            elif "two_factor" in current_url or "2fa" in page_source or "verification" in page_source:
                logging.error("❌ Two-factor authentication required - use manual login")
            elif "captcha" in page_source or "security check" in page_source:
                logging.error("❌ CAPTCHA or security check detected - use manual login")
            elif "verify" in current_url or "confirm" in current_url:
                logging.error("❌ Email/phone verification required - use manual login")
            else:
                # Check for standard error messages
                error_message = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='login_error_message']")
                if error_message:
                    logging.error(f"Facebook login error message: {error_message[0].text}")
                else:
                    logging.error("Login failed: Timeout waiting for post-login page or element.")
            
            login_successful = False

    except (NoSuchElementException, TimeoutException) as e:
        logging.error(f"Selenium element error during login: {e}")
        login_successful = False
    except WebDriverException as e:
        logging.error(f"WebDriver error during login: {e}")
        login_successful = False
    except Exception as e:
        logging.error(f"An unexpected error occurred during login: {e}")
        login_successful = False

    if login_successful:
         pass

    return login_successful

def _get_url_via_share_copy_link(driver: WebDriver, post_element: Any) -> str | None:
    """
    Extract post URL by clicking Share -> Copy link.
    Returns the copied URL or None if failed.
    """
    try:
        # Look for share button with more variations
        share_selectors = [
            ".//div[@aria-label='Send this to friends or post it on your profile.']",
            ".//span[text()='Share']",
            ".//span[@data-ad-rendering-role='share_button']",
            ".//div[@role='button']//span[contains(text(), 'Share')]",
            ".//a[contains(@aria-label, 'Share')]",
            ".//div[contains(@aria-label, 'Share')]",
            ".//span[contains(text(), 'Chia sẻ')]",  # Vietnamese
            ".//span[contains(text(), 'Partager')]",  # French
            ".//span[contains(text(), 'Compartir')]",  # Spanish
            ".//div[@role='button'][.//span[contains(text(), 'Share')]]",
            ".//button[contains(@aria-label, 'Share')]"
        ]
        
        share_button = None
        for selector in share_selectors:
            try:
                share_button = post_element.find_element(By.XPATH, selector)
                break
            except NoSuchElementException:
                continue
        
        if not share_button:
            return None
            
        # Clear clipboard
        try:
            pyperclip.copy("")
        except:
            pass
            
        # Click share button
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", share_button)
        time.sleep(0.5)
        share_button.click()
        time.sleep(2)
        
        # Look for "Copy link" option
        copy_link_selectors = [
            "//span[contains(text(), 'Copy link')]",
            "//div[@role='button']//span[text()='Copy link']",
            "//*[contains(text(), 'Copy link')]"
        ]
        
        copy_link_button = None
        for selector in copy_link_selectors:
            try:
                copy_link_button = driver.find_element(By.XPATH, selector)
                break
            except NoSuchElementException:
                continue
        
        if not copy_link_button:
            # Close menu
            ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            return None
            
        # Click copy link
        copy_link_button.click()
        time.sleep(1)
        
        # Get copied URL
        try:
            copied_url = pyperclip.paste()
            if copied_url and "facebook.com" in copied_url:
                parsed = urlparse(copied_url)
                if parsed.netloc and 'facebook.com' in parsed.netloc:
                    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    return clean_url
        except Exception:
            pass
            
        return None
        
    except Exception as e:
        logging.debug(f"Share/copy failed: {e}")
        return None
    finally:
        # Close any open menus
        try:
            ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            time.sleep(0.3)
        except:
            pass



@production_retry()
def _get_post_identifiers_from_element(driver: WebDriver, post_element: Any, group_url_for_logging: str) -> tuple[str | None, str | None, bool]:
    """
    Extracts post_url and post_id from a Selenium WebElement.
    Also determines if the element is likely a valid post.
    This function is called by the main thread.
    """
    post_url = None
    post_id = None
    is_valid_post_candidate = False

    try:
        link_elements = post_element.find_elements(POST_PERMALINK_XPATH_S[0], POST_PERMALINK_XPATH_S[1])
        logging.debug(f"Found {len(link_elements)} link elements in post")
        if link_elements:
            raw_url = link_elements[0].get_attribute('href')
            if raw_url:
                parsed_url = urlparse(raw_url)
                if "facebook.com" in parsed_url.netloc:
                    # Only accept URLs with /posts/ in them
                    if '/posts/' in parsed_url.path:
                        post_url = parsed_url.scheme + "://" + parsed_url.netloc + parsed_url.path
                        is_valid_post_candidate = True

                        path_parts = parsed_url.path.split('/')
                        if 'posts' in path_parts:
                            try:
                                id_candidate = path_parts[path_parts.index('posts') + 1]
                                if id_candidate.isdigit() or re.match(r'^[a-zA-Z0-9._-]+$', id_candidate):
                                    post_id = id_candidate
                            except IndexError:
                                pass
                    
                        if not post_id:
                            query_params = parse_qs(parsed_url.query)
                            for q_param in ['story_fbid', 'fbid', 'id']:
                                if q_param in query_params and query_params[q_param][0].strip():
                                    post_id = query_params[q_param][0]
                                    break
                    
                    if not post_id:
                        id_match = re.search(r'/(\d{10,})/?', parsed_url.path)
                        if id_match:
                            post_id = id_match.group(1)
        
        if not is_valid_post_candidate:
            # Check if this looks like a post container with content
            try:
                # Look for any text content or images - basic post indicators
                has_text = len(post_element.text.strip()) > 5  # Lower threshold
                has_images = len(post_element.find_elements(By.TAG_NAME, "img")) > 0
                has_links = len(post_element.find_elements(By.TAG_NAME, "a")) > 0
                has_divs = len(post_element.find_elements(By.TAG_NAME, "div")) > 3  # Structural indicator
                
                if has_text or has_images or has_links or has_divs:
                    logging.info(f"Found content indicators (text={has_text}, images={has_images}, links={has_links}, divs={has_divs}), marking as valid candidate")
                    is_valid_post_candidate = True
                else:
                    logging.debug(f"No content indicators found, not a valid candidate")
                    is_valid_post_candidate = False
            except Exception:
                # If we can't check content, assume it's valid and let Share->Copy try
                logging.info(f"Could not check content, assuming valid candidate for Share->Copy")
                is_valid_post_candidate = True

        # Share->Copy method removed - only use direct permalink detection
        # This is much more reliable and eliminates the noise in logs

        if is_valid_post_candidate and not post_id:
            try:
                post_id = f"generated_{uuid.uuid4().hex[:12]}"
                logging.debug(f"Generated fallback post_id: {post_id} for post at {post_url or 'unknown URL'} in group {group_url_for_logging}")
            except Exception as e_gen_id:
                logging.warning(f"Could not generate fallback post_id: {e_gen_id}")
                post_id = f"generated_{int(time.time())}_{uuid.uuid4().hex[:6]}"


    except NoSuchElementException:
        logging.debug(f"Could not find standard post link/identifier elements in group {group_url_for_logging}.")
        is_valid_post_candidate = False
    except Exception as e:
        # Stale element errors are normal - just skip silently
        logging.debug(f"Stale element skipped in group {group_url_for_logging}: {type(e).__name__}")
        is_valid_post_candidate = False

    return post_url, post_id, is_valid_post_candidate

def _extract_data_from_post_html(
    post_html_content: str,
    post_url_from_main: str | None,
    post_id_from_main: str | None,
    group_url_context: str,
    fields_to_scrape: List[str] | None = None
) -> Dict[str, Any] | None:
    """
    Extracts detailed information from a post's HTML content using BeautifulSoup.
    Selectively scrapes fields based on fields_to_scrape.
    This function is executed by worker threads and does not use Selenium WebDriver.
    """
    soup = BeautifulSoup(post_html_content, 'html.parser')
    post_data = {
        "facebook_post_id": post_id_from_main,
        "post_url": post_url_from_main,
        "content_text": "N/A",
        "posted_at": None,
        "scraped_at": datetime.now().isoformat(),
        "post_author_name": None,
        "post_author_profile_pic_url": None,
        "post_image_url": None,
        "comments": []
    }


    scrape_all_fields = not fields_to_scrape

    if scrape_all_fields or "post_author_profile_pic_url" in fields_to_scrape:
        try:
            author_pic_el = soup.select_one(AUTHOR_PROFILE_PIC_BS)
            if author_pic_el:
                if author_pic_el.name == 'image' and author_pic_el.has_attr('xlink:href'):
                    post_data["post_author_profile_pic_url"] = author_pic_el['xlink:href']
                elif author_pic_el.name == 'img' and author_pic_el.has_attr('src'):
                    post_data["post_author_profile_pic_url"] = author_pic_el['src']
        except Exception as e:
            logging.debug(f"BS: Could not extract author profile picture for post {post_id_from_main}: {e}")

    if scrape_all_fields or "post_author_name" in fields_to_scrape:
        try:
            author_name_el = soup.select_one(AUTHOR_NAME_BS)
            if author_name_el:
                post_data["post_author_name"] = author_name_el.get_text(strip=True)
        except Exception as e:
            logging.debug(f"BS: Could not extract author name for post {post_id_from_main}: {e}")

    if scrape_all_fields or "content_text" in fields_to_scrape:
        try:
            text_content = "N/A"
            text_container = soup.select_one(POST_TEXT_CONTAINER_BS)
            if text_container:
                parts = []
                for elem in text_container.find_all(string=False, recursive=False):
                    if not elem.find(['button', 'a'], attrs={'role': 'button'}):
                        elem_text = elem.get_text(separator=' ', strip=True)
                        if elem_text:
                            parts.append(elem_text)
                if parts:
                    text_content = '\n'.join(parts)
                else:
                    text_content = text_container.get_text(separator=' ', strip=True)
            
            if not text_content or text_content == "N/A":
                generic_text_div = soup.select_one(GENERIC_TEXT_DIV_BS)
                if generic_text_div:
                    text_content = generic_text_div.get_text(separator=' ', strip=True)
            
            post_data["content_text"] = text_content if text_content and text_content.strip() else "N/A"
        except Exception as e:
            logging.error(f"BS: Error extracting post text for {post_id_from_main}: {e}", exc_info=True)
            post_data["content_text"] = "N/A"
    
    # Generate DETERMINISTIC content hash for duplicate detection
    # Normalize content to ensure consistent hashing across runs
    content_for_hash = post_data["content_text"] or ""
    # Remove extra whitespace, normalize line endings, strip
    normalized_content = ' '.join(content_for_hash.split())
    post_data["content_hash"] = hashlib.md5(normalized_content.encode('utf-8')).hexdigest()

    if scrape_all_fields or "post_image_url" in fields_to_scrape:
        try:
            img_el = soup.select_one(POST_IMAGE_BS)
            if img_el:
                if img_el.name == 'img' and img_el.has_attr('src'):
                    post_data["post_image_url"] = img_el['src']
                elif img_el.name == 'div' and img_el.has_attr('style'):
                    style_attr = img_el['style']
                    match = re.search(r'background-image:\s*url\("?([^")]*)"?\)', style_attr)
                    if match:
                        post_data["post_image_url"] = match.group(1)
        except Exception as e:
            logging.debug(f"BS: Could not extract post image for {post_id_from_main}: {e}")

    if scrape_all_fields or "posted_at" in fields_to_scrape:
        try:
            raw_timestamp = None
            abbr_el = soup.select_one(POST_TIMESTAMP_ABBR_BS)
            if abbr_el and abbr_el.get('title'):
                raw_timestamp = abbr_el.get('title')
                logging.debug(f"BS: Timestamp from abbr[@title]: {raw_timestamp} for post {post_id_from_main}")

            if not raw_timestamp:
                time_link_el = soup.select_one(POST_TIMESTAMP_LINK_TEXT_BS)
                if time_link_el:
                    raw_timestamp = time_link_el.get_text(strip=True)
                    logging.debug(f"BS: Timestamp from specific link text: {raw_timestamp} for post {post_id_from_main}")

            if not raw_timestamp:
                potential_time_links = soup.select('div[role="article"] a[href*="/posts/"], div[role="article"] a[aria-label]')
                for link in potential_time_links:
                    link_title = link.get('title')
                    if link_title and len(link_title) > 5:
                        if dateparser.parse(link_title, settings={'STRICT_PARSING': False}):
                            raw_timestamp = link_title
                            logging.debug(f"BS: Timestamp from potential link title: {raw_timestamp} for post {post_id_from_main}")
                            break
                    
                    if raw_timestamp: break

                    link_aria_label = link.get('aria-label')
                    if link_aria_label and len(link_aria_label) > 5:
                         if dateparser.parse(link_aria_label, settings={'STRICT_PARSING': False}):
                            raw_timestamp = link_aria_label
                            logging.debug(f"BS: Timestamp from potential link aria-label: {raw_timestamp} for post {post_id_from_main}")
                            break
                    
                    if raw_timestamp: break

                    link_text = link.get_text(strip=True)
                    if link_text and len(link_text) > 2 and len(link_text) < 30 and not (link_text.lower() == post_data.get("post_author_name","").lower() or "comment" in link_text.lower()):
                        if dateparser.parse(link_text, settings={'STRICT_PARSING': False}):
                            raw_timestamp = link_text
                            logging.debug(f"BS: Timestamp from potential link text: {raw_timestamp} for post {post_id_from_main}")
                            break
                if not raw_timestamp:
                     logging.debug(f"BS: All timestamp extraction methods failed for post {post_id_from_main}")
            
            if raw_timestamp:
                parsed_dt = None  # Timestamp parsing disabled
                if parsed_dt:
                    post_data["posted_at"] = parsed_dt.isoformat()
                    logging.debug(f"BS: Successfully parsed timestamp '{raw_timestamp}' to '{post_data['posted_at']}' for post {post_id_from_main}")
                else:
                    logging.warning(f"BS: Failed to parse raw timestamp '{raw_timestamp}' for post {post_id_from_main}")
                    post_data["posted_at"] = None
            else:
                 logging.debug(f"BS: Could not extract any raw timestamp string for post {post_id_from_main}")
                 post_data["posted_at"] = None
        except Exception as e:
            logging.warning(f"BS: Error during timestamp extraction for post {post_id_from_main}: {e}", exc_info=True)
            post_data["posted_at"] = None

    if scrape_all_fields or "comments" in fields_to_scrape:
        try:
            comment_elements_soup = soup.select(COMMENT_CONTAINER_BS)
            for comment_s_el in comment_elements_soup:
                comment_details = {
                    'commenterProfilePic': None, 'commenterName': None,
                    'commentText': "N/A", 'commentFacebookId': None, 'comment_timestamp': None
                }
                if scrape_all_fields or "commenterProfilePic" in fields_to_scrape:
                    commenter_pic_s_el = comment_s_el.select_one(COMMENTER_PROFILE_PIC_BS)
                    if commenter_pic_s_el:
                        if commenter_pic_s_el.name == 'image' and commenter_pic_s_el.has_attr('xlink:href'):
                            comment_details['commenterProfilePic'] = commenter_pic_s_el['xlink:href']
                        elif commenter_pic_s_el.name == 'img' and commenter_pic_s_el.has_attr('src'):
                            comment_details['commenterProfilePic'] = commenter_pic_s_el['src']
                
                if scrape_all_fields or "commenterName" in fields_to_scrape:
                    commenter_name_s_el = comment_s_el.select_one(COMMENTER_NAME_BS)
                    if commenter_name_s_el:
                        comment_details['commenterName'] = commenter_name_s_el.get_text(strip=True)

                if scrape_all_fields or "commentText" in fields_to_scrape:
                    comment_text_s_el = comment_s_el.select_one(COMMENT_TEXT_PRIMARY_BS)
                    if comment_text_s_el:
                        comment_details['commentText'] = comment_text_s_el.get_text(strip=True)
                    else:
                        fb_text_container = comment_s_el.select_one(COMMENT_TEXT_CONTAINER_FALLBACK_BS)
                        if fb_text_container:
                            actual_text_el = fb_text_container.select_one(COMMENT_ACTUAL_TEXT_FALLBACK_BS)
                            if actual_text_el:
                                 comment_details['commentText'] = actual_text_el.get_text(strip=True)
                            elif fb_text_container.get_text(strip=True):
                                 comment_details['commentText'] = fb_text_container.get_text(strip=True)

                if scrape_all_fields or "commentFacebookId" in fields_to_scrape:
                    comment_id_link = comment_s_el.select_one(COMMENT_ID_LINK_BS)
                    if comment_id_link and comment_id_link.has_attr('href'):
                        parsed_comment_url = urlparse(comment_id_link['href'])
                        comment_id_qs = parse_qs(parsed_comment_url.query)
                        if 'comment_id' in comment_id_qs:
                            comment_details['commentFacebookId'] = comment_id_qs['comment_id'][0]
                    if not comment_details['commentFacebookId'] and comment_s_el.has_attr('data-commentid'):
                         comment_details['commentFacebookId'] = comment_s_el['data-commentid']
                    if not comment_details['commentFacebookId']:
                         comment_details['commentFacebookId'] = f"bs_fallback_{uuid.uuid4().hex[:10]}"


                if scrape_all_fields or "comment_timestamp" in fields_to_scrape:
                    raw_comment_time = None
                    comment_time_abbr_el = comment_s_el.select_one(COMMENT_TIMESTAMP_ABBR_BS)
                    if comment_time_abbr_el and comment_time_abbr_el.get('title'):
                        raw_comment_time = comment_time_abbr_el['title']
                    else:
                        comment_time_link_el = comment_s_el.select_one(COMMENT_TIMESTAMP_LINK_BS)
                        if comment_time_link_el:
                            raw_comment_time = comment_time_link_el.get('aria-label') or comment_time_link_el.get_text(strip=True)
                    if raw_comment_time:
                        parsed_comment_dt = None  # Timestamp parsing disabled
                        comment_details['comment_timestamp'] = parsed_comment_dt.isoformat() if parsed_comment_dt else None
                
                if comment_details['commenterName'] or (comment_details['commentText'] and comment_details['commentText'] != "N/A"):
                    post_data["comments"].append(comment_details)
            logging.debug(f"BS: Extracted {len(post_data['comments'])} comments for post {post_id_from_main}")
        except Exception as e:
            logging.warning(f"BS: Error extracting comments for post {post_id_from_main}: {e}")

    if (post_data["post_url"] or post_data["facebook_post_id"]) and \
       (post_data["content_text"] != "N/A" or post_data["posted_at"] is not None or post_data["post_author_name"] is not None):
        return post_data
    else:
        logging.debug(f"BS: Skipping post {post_id_from_main} due to missing essential data (URL/ID, Text, Time, Author).")
        return None


def scrape_authenticated_group(
    driver: WebDriver,
    group_url: str,
    num_posts: int,
    fields_to_scrape: List[str] | None = None,
    stop_at_url: str | None = None
) -> Iterator[Dict[str, Any]]:
    """
    Scrapes posts from a Facebook group, yielding data for each post.
    Uses parallel processing for HTML parsing and selective field scraping.

    Args:
        driver: An initialized and authenticated Selenium WebDriver instance.
        group_url: The URL of the Facebook group.
        num_posts: The number of posts to attempt to scrape.

    Returns:
        A list of dictionaries, each representing a post with essential information.
    """
    # Setup virtual display for clipboard operations (headless mode)
    virtual_display_setup = setup_virtual_display()
    if virtual_display_setup:
        logging.info("🖥️ Virtual display ready - clipboard operations enabled")
    else:
        logging.warning("⚠️ Virtual display not available - Share->Copy may not work")
    
    # Ensure chronological sorting for newest posts first
    if '?' in group_url:
        chronological_url = f"{group_url}&sorting_setting=CHRONOLOGICAL"
    else:
        chronological_url = f"{group_url}?sorting_setting=CHRONOLOGICAL"
    
    logging.info(f"Navigating to group: {chronological_url} (chronological sorting)")
    try:
        driver.get(chronological_url)
        logging.debug(f"Successfully navigated to {group_url}")
        
        # Wait for page to load before scraping group name
        WebDriverWait(driver, 30).until(
             EC.presence_of_element_located(FEED_OR_SCROLLER_S)
        )
        logging.debug("Feed element found.")
        
        # Get or create group (driver is now on the correct page)
        from database.simple_per_group import get_most_recent_post_content_hash, get_or_create_group, _scrape_group_name_from_page
        from database.crud import get_db_connection
        
        db_conn = get_db_connection()
        group_id, table_suffix = get_or_create_group(db_conn, group_url)  # Create with fallback name first
        
        # Check if this group has a fallback name - if so, scrape the real name
        cursor = db_conn.cursor()
        cursor.execute("SELECT group_name FROM Groups WHERE group_id = ?", (group_id,))
        current_name = cursor.fetchone()[0]
        
        if current_name.startswith("Group from "):
            logging.info(f"📝 Scraping group name (first time)...")
            scraped_name = _scrape_group_name_from_page(driver)
            if scraped_name:
                cursor.execute("UPDATE Groups SET group_name = ? WHERE group_id = ?", (scraped_name, group_id))
                db_conn.commit()
                logging.info(f"✅ Updated group name to: '{scraped_name}'")
            else:
                logging.warning(f"❌ Could not scrape group name, keeping fallback")
        
        processed_post_urls: set[str] = set()
        processed_post_ids: set[str] = set()
        processed_content_hashes: set[str] = set()
        
        # Get most recent content hash for incremental scraping (FIXED normalization)
        most_recent_hash = get_most_recent_post_content_hash(db_conn, table_suffix)
        duplicate_found = False  # Global flag to stop all processing
        
        if most_recent_hash:
            logging.info(f"🔄 Incremental scraping: will stop when finding duplicate content")
        else:
            logging.info(f"🆕 No existing posts found - this is a fresh scrape")

        if "groups/" not in driver.current_url or "not_found" in driver.current_url or "login" in driver.current_url or "checkpoint" in driver.current_url:
             logging.error(f"❌ LOGGED OUT! Cannot access group. Current URL: {driver.current_url}")
             logging.error(f"❌ Session is invalid - Facebook redirected to login/checkpoint")
             logging.error(f"❌ You need to refresh your cookies!")
             
             # Send Telegram notification about session failure
             try:
                 from config import get_telegram_settings
                 from notifier.telegram_notifier import broadcast_message
                 bot_token, chat_ids = get_telegram_settings()
                 if bot_token and chat_ids:
                     error_msg = f"""🚨 <b>Facebook Session Expired!</b>
                       
❌ Bot cannot access Facebook group
🔒 Cookies have expired or session is invalid

💡 <b>To fix via Telegram:</b>
1. Send: <code>/login</code>
2. Choose 'manual' or 'auto'
3. Complete login process
4. Bot will continue automatically

🌐 Current URL: <code>{driver.current_url}</code>"""
                     
                     broadcast_message(bot_token, chat_ids, error_msg, parse_mode="HTML")
                     logging.info("📱 Sent session failure notification to Telegram")
             except Exception as e:
                 logging.error(f"Failed to send Telegram notification: {e}")
             
             return


        extracted_count = 0
        max_scroll_attempts = 50
        consecutive_no_new_posts = 0
        MAX_CONSECUTIVE_NO_POSTS = 3
        MAX_WORKERS = 5
        
        logging.info(f"Starting to scrape up to {num_posts} posts from {group_url} using {MAX_WORKERS} workers...")

        scroll_attempt = 0
        last_on_page_post_count = 0

        # Collect posts to yield in reverse order (newest first in DB)
        collected_posts = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            active_futures: List[concurrent.futures.Future] = []

            while extracted_count < num_posts and scroll_attempt < max_scroll_attempts:
                scroll_attempt += 1
                
                driver.execute_script("window.scrollBy(0, window.innerHeight * 0.8);")
                time.sleep(1.5)

                try:
                    WebDriverWait(driver, 15).until(
                        lambda d: len(d.find_elements(POST_CONTAINER_S[0], POST_CONTAINER_S[1])) > last_on_page_post_count or \
                                  (scroll_attempt > 1 and len(d.find_elements(POST_CONTAINER_S[0], POST_CONTAINER_S[1])) == last_on_page_post_count)
                    )
                except TimeoutException:
                    logging.debug(f"Scroll attempt {scroll_attempt}: No new posts appeared after scroll or timeout.")
                
                overlay_container_selectors = [
                    "//div[@data-testid='dialog']", "//div[contains(@role, 'dialog')]",
                    "//div[contains(@aria-label, 'Save your login info')]", "//div[contains(@aria-label, 'Turn on notifications')]",
                    "//div[@aria-label='View site information']"
                ]
                for overlay_selector_xpath in overlay_container_selectors:
                    try:
                        
                        
                        
                        
                        dismiss_button_xpaths = [
                            ".//button[text()='Not Now']",
                            ".//button[contains(text(),'Not now')]",
                            ".//button[contains(text(),'Not Now')]",
                            ".//a[@aria-label='Close']",
                            ".//button[@aria-label='Close']",
                            ".//button[contains(@aria-label, 'close')]",
                            ".//div[@role='button'][@aria-label='Close']",
                            ".//button[contains(text(), 'Close')]",
                            ".//button[contains(text(), 'Dismiss')]",
                            ".//button[contains(text(), 'Later')]",
                            ".//div[@role='button'][contains(text(), 'Not Now')]",
                            ".//div[@role='button'][contains(text(), 'Later')]",
                            ".//div[@aria-label='Close' and @role='button']",
                            ".//i[@aria-label='Close dialog']"
                        ]

                        potential_overlays = driver.find_elements(By.XPATH, overlay_selector_xpath)
                        
                        for overlay_candidate in potential_overlays:
                            if overlay_candidate.is_displayed():
                                logging.debug(f"Visible overlay detected with selector: {overlay_selector_xpath}. Attempting to dismiss.")
                                dismissed_this_one = False
                                for btn_xpath in dismiss_button_xpaths:
                                    try:
                                        dismiss_button = WebDriverWait(overlay_candidate, 1).until(
                                            EC.element_to_be_clickable((By.XPATH, btn_xpath))
                                        )
                                        if dismiss_button.is_displayed() and dismiss_button.is_enabled():
                                            driver.execute_script("arguments[0].click();", dismiss_button)
                                            logging.debug(f"Clicked dismiss button ('{btn_xpath}') in overlay {overlay_selector_xpath}.")
                                            WebDriverWait(driver, 5).until(EC.invisibility_of_element(overlay_candidate))
                                            logging.debug(f"Overlay {overlay_selector_xpath} confirmed dismissed.")
                                            dismissed_this_one = True
                                            break
                                    except (TimeoutException, NoSuchElementException):
                                        logging.debug(f"Dismiss button '{btn_xpath}' not found or not clickable in overlay {overlay_selector_xpath}.")
                                    except StaleElementReferenceException:
                                        logging.info(f"Overlay or button became stale during dismissal attempt for {overlay_selector_xpath}, likely dismissed.")
                                        dismissed_this_one = True
                                        break
                                    except Exception as e_dismiss:
                                        logging.error(f"Error clicking dismiss button '{btn_xpath}' in overlay {overlay_selector_xpath}: {e_dismiss}")
                                if dismissed_this_one:
                                    break
                        
                    except Exception as e_overlay_check:
                        logging.debug(f"Error checking/processing overlay selector {overlay_selector_xpath}: {e_overlay_check}")


                current_post_elements = driver.find_elements(POST_CONTAINER_S[0], POST_CONTAINER_S[1])
                
                if len(current_post_elements) > last_on_page_post_count:
                    consecutive_no_new_posts = 0
                else:
                    consecutive_no_new_posts += 1
                    if consecutive_no_new_posts >= MAX_CONSECUTIVE_NO_POSTS:
                        logging.info(f"No new posts found for {consecutive_no_new_posts} consecutive scrolls. Stopping scroll.")
                        break
                
                last_on_page_post_count = len(current_post_elements)
                logging.info(f"Scroll {scroll_attempt}: Found {last_on_page_post_count} potential posts. Scraped: {extracted_count}/{num_posts}. Active tasks: {len(active_futures)}.")

                # Track how many posts we've submitted for processing
                posts_submitted_this_batch = 0
                
                for post_element in current_post_elements:
                    if extracted_count >= num_posts: break
                    if posts_submitted_this_batch >= num_posts: break  # Don't over-process

                    temp_post_url, temp_post_id, is_candidate = _get_post_identifiers_from_element(driver, post_element, group_url)

                    if not is_candidate:
                        logging.debug(f"Element skipped as not a valid post candidate: URL={temp_post_url}, ID={temp_post_id}")
                        continue

                    unique_key_url = temp_post_url if temp_post_url else f"no_url_{temp_post_id}"
                    unique_key_id = temp_post_id if temp_post_id else f"no_id_{temp_post_url}"

                    if (temp_post_url and temp_post_url in processed_post_urls) or \
                       (temp_post_id and temp_post_id in processed_post_ids):
                        continue
                    
                    # Process all posts regardless of URL availability
                    # URLs are nice to have but not required for content processing
                    
                    # For incremental scraping, we'll check content hash after extraction
                    # No early stopping here - we need the content first

                    # First, try to click "See more" to expand content
                    try:
                        see_more_button = WebDriverWait(post_element, 1).until(
                            EC.element_to_be_clickable(SEE_MORE_BUTTON_XPATH_S)
                        )
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", see_more_button)
                        time.sleep(0.2)
                        see_more_button = WebDriverWait(post_element, 1).until(EC.element_to_be_clickable(see_more_button))
                        see_more_button.click()
                        time.sleep(0.5)
                        logging.info(f"✅ Clicked 'See more' for post {temp_post_id or temp_post_url}")
                    except (TimeoutException, NoSuchElementException):
                        logging.info(f"ℹ️ No 'See more' button found for post {temp_post_id or temp_post_url}")
                    except Exception as e_sm:
                        logging.warning(f"❌ Error clicking 'See more' for {temp_post_id or temp_post_url}: {e_sm}")
                    
                    # NOW get the HTML content (after clicking "See more" if it existed)
                    post_html_content = post_element.get_attribute('outerHTML')
                    if not post_html_content:
                        logging.warning(f"Could not get outerHTML for post {temp_post_id or temp_post_url}. Skipping.")
                        continue

                    if temp_post_url: processed_post_urls.add(temp_post_url)
                    if temp_post_id: processed_post_ids.add(temp_post_id)
                    
                    future = executor.submit(_extract_data_from_post_html, post_html_content, temp_post_url, temp_post_id, group_url, fields_to_scrape)
                    active_futures.append(future)
                    posts_submitted_this_batch += 1
                
                completed_futures_in_batch = [f for f in active_futures if f.done()]
                for future in completed_futures_in_batch:
                    active_futures.remove(future)
                    if extracted_count >= num_posts: continue

                    try:
                        result = future.result(timeout=1)
                        if result:
                            # DUPLICATE check - stop immediately on ANY duplicate (incremental scraping)
                            if most_recent_hash and result.get('content_hash') == most_recent_hash:
                                logging.info(f"🛑 Found duplicate content (hash: {most_recent_hash[:8]}...)")
                                logging.info(f"🎯 Incremental scraping complete - stopping at duplicate")
                                duplicate_found = True
                                extracted_count = num_posts  # Force completion
                                break
                            
                            # Only add NON-duplicate posts
                            collected_posts.append(result)
                            extracted_count += 1
                            logging.debug(f"Collected post {extracted_count}/{num_posts} (ID: {result.get('facebook_post_id')}) by worker.")
                            
                            # Log progress for incremental scraping
                            if extracted_count == 1 and most_recent_hash:
                                logging.info(f"✅ First post is new - continuing incremental scrape")
                                
                    except concurrent.futures.TimeoutError:
                        logging.warning("Timeout getting result from a future. Will retry or discard later.")
                        active_futures.append(future)
                    except Exception as e_future:
                        logging.error(f"Error processing a post in worker thread: {e_future}", exc_info=True)
                
                if extracted_count >= num_posts:
                    logging.info(f"Target of {num_posts} posts reached. Finalizing...")
                    break
            
            logging.info(f"Scroll attempts finished or target reached. Waiting for {len(active_futures)} remaining tasks...")
            for future in concurrent.futures.as_completed(active_futures, timeout=30):
                if extracted_count >= num_posts or duplicate_found: break
                try:
                    result = future.result()
                    if result:
                        # DUPLICATE check in final collection too
                        if most_recent_hash and result.get('content_hash') == most_recent_hash:
                            logging.info(f"🛑 Found duplicate content in final collection (hash: {most_recent_hash[:8]}...)")
                            logging.info(f"🎯 Incremental scraping complete - stopping final collection")
                            duplicate_found = True
                            break
                            
                        collected_posts.append(result)
                        extracted_count += 1
                        logging.debug(f"Collected post {extracted_count}/{num_posts} (ID: {result.get('facebook_post_id')}) during final collection.")
                except Exception as e_final_future:
                    logging.error(f"Error in final collection from worker: {e_final_future}", exc_info=True)
        
        # Yield posts in reverse order so newest gets highest DB ID
        logging.info(f"Yielding {len(collected_posts)} posts in reverse order (newest gets highest ID)")
        for post in reversed(collected_posts):
            yield post
        
        logging.info(f"Finished scraping generator. Total posts yielded: {len(collected_posts)}.")
        if len(collected_posts) < num_posts:
             logging.warning(f"Generator finished, but only yielded {len(collected_posts)} posts, less than requested {num_posts}.")

    except TimeoutException:
        logging.error(f"Main thread timed out waiting for elements while scraping group {group_url}.")
    except NoSuchElementException:
         logging.error(f"Main thread could not find expected elements while scraping group {group_url}. Selectors may be outdated.")
    except WebDriverException as e:
        logging.error(f"A WebDriver error occurred during group scraping: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred during group scraping: {e}", exc_info=True)
    finally:
        # Cleanup virtual display
        if virtual_display_setup:
            cleanup_virtual_display()


@production_retry()
def is_facebook_session_valid(driver: WebDriver) -> bool:
    """
    Performs a basic check to see if the current Facebook session in the driver is still active.
    """
    try:
        logging.info("Checking Facebook session validity...")
        driver.get("https://www.facebook.com/settings")
        WebDriverWait(driver, 10).until(
            EC.url_contains("settings")
            or EC.presence_of_element_located((By.CSS_SELECTOR, "div[aria-label='Facebook']"))
        )
        logging.debug("Session appears valid.")
        return True
    except TimeoutException:
        logging.warning("Session check timed out or redirected to login. Session may be invalid.")
        return False
    except WebDriverException as e:
        logging.error(f"WebDriver error during session check: {e}")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred during session check: {e}")
        return False