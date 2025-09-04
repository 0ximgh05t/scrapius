#!/usr/bin/env python3
"""
Telegram Command Handlers for Scrapius Bot
Handles all user commands and interactions cleanly separated from main bot logic.
"""

import logging
import requests
from typing import Dict, List, Optional

from notifier.telegram_notifier import send_telegram_message
from database.crud import botsettings_get, botsettings_set
from database.simple_per_group import list_all_groups, get_or_create_group, drop_group_table
from config import (
    get_working_hours_settings, get_reliability_settings, 
    is_within_working_hours, get_next_working_time,
    get_cookie_store_path, create_reliable_webdriver
)
from scraper.session_persistence import save_cookies, load_cookies
from scraper.facebook_scraper_headless import login_to_facebook, is_facebook_session_valid


class CommandHandlers:
    """Handles all Telegram bot commands and interactions."""
    
    def __init__(self):
        self.login_states = {}
        self.login_drivers = {}
        self.login_credentials = {}
    
    async def handle_text_command(self, cmd: Dict, bot_token: str, conn) -> None:
        """Handle text-based commands."""
        chat_id = cmd['chat_id']
        command = cmd['cmd']
        arg = cmd.get('arg', '')
        
        # Handle login flow states
        if chat_id in self.login_states:
            await self._handle_login_flow(bot_token, chat_id, conn, command, arg)
            return
        
        # Regular commands
        if command == '/start':
            await self._handle_start(bot_token, chat_id, conn)
        elif command == '/config':
            await self._handle_config(bot_token, chat_id, conn, arg)
        elif command == '/groups':
            await self._handle_groups(bot_token, chat_id, conn)
        elif command == '/addgroup':
            await self._handle_addgroup(bot_token, chat_id, conn, arg)
        elif command == '/removegroup':
            await self._handle_removegroup(bot_token, chat_id, conn, arg)
        elif command == '/sethours':
            await self._handle_sethours(bot_token, chat_id, conn, arg)
        elif command == '/settiming':
            await self._handle_settiming(bot_token, chat_id, conn, arg)
        elif command == '/setlimit':
            await self._handle_setlimit(bot_token, chat_id, conn, arg)
        elif command == '/setposts':
            await self._handle_setposts(bot_token, chat_id, conn, arg)
        elif command == '/login':
            await self._handle_login(bot_token, chat_id, conn)
        # NEW: Prompt setting commands
        elif command == '/prompt':
            await self._handle_prompt(bot_token, chat_id, conn)
        elif command == '/setsystem':
            await self._handle_setsystem(bot_token, chat_id, conn, arg)
        elif command == '/setprompt':
            await self._handle_setprompt(bot_token, chat_id, conn, arg)
        # NEW: Cookie management commands
        elif command == '/cookies':
            await self._handle_cookies(bot_token, chat_id, conn)
        elif command == '/clearcookies':
            await self._handle_clearcookies(bot_token, chat_id, conn)
        else:
            send_telegram_message(bot_token, chat_id, "❓ Unknown command. Use /start for help.")
    
    async def handle_callback_query(self, update: Dict, bot_token: str, chat_ids: List[str], conn) -> None:
        """Handle button callback queries."""
        callback_data = update['callback_query']['data']
        callback_query_id = update['callback_query']['id']
        
        # Get chat_id from message (same as text commands), not from user
        chat_id = str(update['callback_query']['message']['chat']['id'])
        
        if chat_id not in chat_ids:
            logging.debug(f"Callback from unauthorized chat: {chat_id}")
            return
        
        # Answer callback query
        def answer_callback(text, show_alert=False):
            answer_url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
            payload = {
                "callback_query_id": callback_query_id,
                "text": text,
                "show_alert": show_alert
            }
            return requests.post(answer_url, json=payload).ok
        
        try:
            if callback_data.startswith('login_'):
                await self._handle_login_callback(callback_data, bot_token, chat_id, conn, answer_callback)
        except Exception as e:
            logging.error(f"Error handling callback {callback_data}: {e}")
            answer_callback(f"❌ Error: {str(e)}")
    
    async def _handle_start(self, bot_token: str, chat_id: str, conn) -> None:
        """Handle /start command."""
        help_text = """🤖 <b>Scrapius Bot Commands:</b>

📋 <b>Groups:</b>
/groups - View monitored groups
/addgroup &lt;url&gt; - Add new group
/removegroup &lt;id&gt; - Remove group

🧠 <b>AI Settings:</b>
/prompt - Show current prompts
/setsystem &lt;text&gt; - Set system prompt
/setprompt &lt;text&gt; - Set user prompt

⚙️ <b>Bot Configuration:</b>
/config - Show all settings
/config hours - Working hours help
/config timing - Timing help
/config limits - Limits help

⏰ <b>Working Hours:</b>
/sethours on/off - Enable/disable working hours
/sethours 8-16 - Set 8:00-16:00 GMT+3

⏱️ <b>Speed & Limits:</b>
/setlimit &lt;number&gt; - Scrapes per hour
/settiming conservative/normal/aggressive - Speed presets
/setposts &lt;number&gt; - Max posts per group

🔐 <b>Facebook Login:</b>
/login - Login to Facebook
/cookies - Check cookie status & expiration
/clearcookies - Clear saved cookies

⚠️ <b>Cookie Expiration:</b> Your cookies expire on <b>September 2, 2026</b>
"""
        send_telegram_message(bot_token, chat_id, help_text, parse_mode="HTML")
    
    async def _handle_config(self, bot_token: str, chat_id: str, conn, arg: str) -> None:
        """Handle /config command."""
        if not arg:
            # Show main config
            working_hours = get_working_hours_settings(conn)
            reliability = get_reliability_settings(conn)
            cur_limit = botsettings_get(conn, 'bot_hourly_limit', '6')
            
            hours_status = "🟢 Active" if is_within_working_hours(conn) else "🔴 Paused"
            next_working = get_next_working_time(conn)
            
            config_msg = f"""⚙️ <b>Bot Configuration</b>

📊 <b>Scraping Settings:</b>
• Hourly Limit: {cur_limit} runs/hour
• Posts per Group: {reliability['max_posts_per_group']}
• Group Delay: {reliability['group_delay']}s
• Post Delay: {reliability['post_processing_delay']}s

⏰ <b>Working Hours:</b> {hours_status}
• Enabled: {'✅' if working_hours['enabled'] else '❌'}
• Hours: {working_hours['start_hour']:02d}:00-{working_hours['end_hour']:02d}:00 GMT+{working_hours['timezone_offset']}
• Status: {next_working}

🔧 <b>Quick Commands:</b>
/config hours - Working hours help
/config timing - Timing help
/config limits - Limits help"""
            
            send_telegram_message(bot_token, chat_id, config_msg, parse_mode="HTML")
        else:
            # Show specific config section
            await self._handle_config_section(bot_token, chat_id, conn, arg.lower())
    
    async def _handle_config_section(self, bot_token: str, chat_id: str, conn, section: str) -> None:
        """Handle specific config sections."""
        if section == 'hours':
            settings = get_working_hours_settings(conn)
            msg = f"""⏰ <b>Working Hours Configuration</b>

Current Settings:
• Status: {'🟢 Enabled' if settings['enabled'] else '🔴 Disabled'}
• Hours: {settings['start_hour']:02d}:00 - {settings['end_hour']:02d}:00
• Timezone: GMT+{settings['timezone_offset']}

<b>Commands:</b>
<code>/sethours on</code> - Enable working hours
<code>/sethours off</code> - Disable (24/7 mode)
<code>/sethours 9-17</code> - Set 9 AM to 5 PM
<code>/sethours 8-16</code> - Set 8 AM to 4 PM"""
            
        elif section == 'timing':
            reliability = get_reliability_settings(conn)
            msg = f"""⏱️ <b>Timing Configuration</b>

Current Settings:
• Group Delay: {reliability['group_delay']}s
• Post Delay: {reliability['post_processing_delay']}s
• Max Retries: {reliability['max_retries']}

<b>Presets:</b>
<code>/settiming conservative</code> - Slow & reliable
<code>/settiming normal</code> - Balanced
<code>/settiming aggressive</code> - Fast but risky

<b>Custom:</b>
<code>/settiming 45</code> - Set group delay to 45s"""
            
        elif section == 'limits':
            reliability = get_reliability_settings(conn)
            cur_limit = botsettings_get(conn, 'bot_hourly_limit', '6')
            msg = f"""📊 <b>Limits Configuration</b>

Current Settings:
• Hourly Limit: {cur_limit} runs/hour
• Posts per Group: {reliability['max_posts_per_group']}

<b>Commands:</b>
<code>/setlimit 4</code> - 4 runs/hour (15 min intervals)
<code>/setlimit 6</code> - 6 runs/hour (10 min intervals)
<code>/setlimit 12</code> - 12 runs/hour (5 min intervals)

<code>/setposts 5</code> - Max 5 posts per group
<code>/setposts 10</code> - Max 10 posts per group"""
        else:
            msg = "❌ Unknown config section. Use: hours, timing, or limits"
        
        send_telegram_message(bot_token, chat_id, msg, parse_mode="HTML")
    
    async def _handle_groups(self, bot_token: str, chat_id: str, conn) -> None:
        """Handle /groups command."""
        groups = list_all_groups(conn)
        if not groups:
            send_telegram_message(bot_token, chat_id, "📋 <b>No groups configured.</b>", parse_mode="HTML")
        else:
            lines = [f"🔹 <b>{g['group_id']}</b>: {g['group_name']} ({g['post_count']} posts)" for g in groups]
            group_text = f"📋 <b>Monitored Groups:</b>\n\n" + "\n".join(lines)
            send_telegram_message(bot_token, chat_id, group_text, parse_mode="HTML")
    
    async def _handle_sethours(self, bot_token: str, chat_id: str, conn, arg: str) -> None:
        """Handle /sethours command."""
        if not arg:
            send_telegram_message(bot_token, chat_id, "📝 <b>Usage:</b> /sethours &lt;on|off|8-16|9-17&gt;", parse_mode="HTML")
            return
        
        arg = arg.lower().strip()
        
        if arg == 'on':
            botsettings_set(conn, 'working_hours_enabled', 'true')
            send_telegram_message(bot_token, chat_id, "✅ <b>Working hours enabled</b>", parse_mode="HTML")
        elif arg == 'off':
            botsettings_set(conn, 'working_hours_enabled', 'false')
            send_telegram_message(bot_token, chat_id, "✅ <b>Working hours disabled</b> - Bot runs 24/7", parse_mode="HTML")
        elif '-' in arg:
            try:
                start, end = arg.split('-')
                start_hour = int(start)
                end_hour = int(end)
                
                if not (0 <= start_hour <= 23 and 0 <= end_hour <= 23 and start_hour < end_hour):
                    raise ValueError("Invalid hours")
                
                botsettings_set(conn, 'working_hours_start', str(start_hour))
                botsettings_set(conn, 'working_hours_end', str(end_hour))
                botsettings_set(conn, 'working_hours_enabled', 'true')
                
                send_telegram_message(bot_token, chat_id, f"✅ <b>Working hours set:</b> {start_hour:02d}:00 - {end_hour:02d}:00 GMT+3", parse_mode="HTML")
            except:
                send_telegram_message(bot_token, chat_id, "❌ <b>Invalid format.</b> Use: /sethours 8-16", parse_mode="HTML")
        else:
            send_telegram_message(bot_token, chat_id, "📝 <b>Usage:</b> /sethours &lt;on|off|8-16|9-17&gt;", parse_mode="HTML")
    
    async def _handle_settiming(self, bot_token: str, chat_id: str, conn, arg: str) -> None:
        """Handle /settiming command."""
        if not arg:
            send_telegram_message(bot_token, chat_id, "📝 <b>Usage:</b> /settiming &lt;conservative|normal|aggressive|seconds&gt;", parse_mode="HTML")
            return
        
        arg = arg.lower().strip()
        
        if arg == 'conservative':
            botsettings_set(conn, 'group_delay', '60')
            botsettings_set(conn, 'post_delay', '2.0')
            send_telegram_message(bot_token, chat_id, "✅ <b>Conservative timing:</b> 60s group delay, 2s post delay", parse_mode="HTML")
        elif arg == 'normal':
            botsettings_set(conn, 'group_delay', '30')
            botsettings_set(conn, 'post_delay', '1.0')
            send_telegram_message(bot_token, chat_id, "✅ <b>Normal timing:</b> 30s group delay, 1s post delay", parse_mode="HTML")
        elif arg == 'aggressive':
            botsettings_set(conn, 'group_delay', '15')
            botsettings_set(conn, 'post_delay', '0.5')
            send_telegram_message(bot_token, chat_id, "⚠️ <b>Aggressive timing:</b> 15s group delay, 0.5s post delay (risky!)", parse_mode="HTML")
        else:
            try:
                delay = int(arg)
                if delay < 5 or delay > 300:
                    raise ValueError("Delay out of range")
                botsettings_set(conn, 'group_delay', str(delay))
                send_telegram_message(bot_token, chat_id, f"✅ <b>Group delay set:</b> {delay}s", parse_mode="HTML")
            except:
                send_telegram_message(bot_token, chat_id, "❌ <b>Invalid value.</b> Use 5-300 seconds", parse_mode="HTML")
    
    async def _handle_setlimit(self, bot_token: str, chat_id: str, conn, arg: str) -> None:
        """Handle /setlimit command."""
        if not arg:
            send_telegram_message(bot_token, chat_id, "📝 <b>Usage:</b> /setlimit &lt;number&gt;", parse_mode="HTML")
            return
        
        try:
            n = int(arg)
            if n < 1:
                raise ValueError
            botsettings_set(conn, 'bot_hourly_limit', str(n))
            send_telegram_message(bot_token, chat_id, f"✅ <b>Hourly limit set:</b> {n}", parse_mode="HTML")
        except:
            send_telegram_message(bot_token, chat_id, "❌ <b>Invalid number.</b> Use positive integer", parse_mode="HTML")
    
    async def _handle_setposts(self, bot_token: str, chat_id: str, conn, arg: str) -> None:
        """Handle /setposts command."""
        if not arg:
            send_telegram_message(bot_token, chat_id, "📝 <b>Usage:</b> /setposts &lt;number&gt;", parse_mode="HTML")
            return
        
        try:
            posts = int(arg)
            if posts < 1 or posts > 50:
                raise ValueError("Posts out of range")
            botsettings_set(conn, 'max_posts_per_group', str(posts))
            send_telegram_message(bot_token, chat_id, f"✅ <b>Posts per group set:</b> {posts}", parse_mode="HTML")
        except:
            send_telegram_message(bot_token, chat_id, "❌ <b>Invalid number.</b> Use 1-50", parse_mode="HTML")
    
    async def _handle_addgroup(self, bot_token: str, chat_id: str, conn, arg: str) -> None:
        """Handle /addgroup command."""
        if not arg:
            send_telegram_message(bot_token, chat_id, "📝 <b>Usage:</b> /addgroup &lt;url&gt;", parse_mode="HTML")
            return
        
        try:
            # Normalize group URL
            norm_url = arg.strip()
            if not norm_url.startswith("https://www.facebook.com/groups/"):
                raise ValueError("Invalid Facebook group URL")
            
            # Remove query parameters and trailing slash
            if '?' in norm_url:
                norm_url = norm_url.split('?')[0]
            norm_url = norm_url.rstrip('/')
            
            # Check group limit
            existing_groups = list_all_groups(conn)
            if len(existing_groups) >= 5:
                send_telegram_message(bot_token, chat_id, "⚠️ <b>Group limit reached!</b> Max 5 groups. Remove one first.", parse_mode="HTML")
                return
            
            group_id, table_suffix = get_or_create_group(conn, norm_url, f"Group from {norm_url}")
            send_telegram_message(bot_token, chat_id, f"✅ <b>Group added!</b>\n\nGroup ID: {group_id}\nTable: Posts_{table_suffix}", parse_mode="HTML")
            
        except Exception as e:
            send_telegram_message(bot_token, chat_id, f"❌ <b>Error adding group:</b> {str(e)}", parse_mode="HTML")
    
    async def _handle_removegroup(self, bot_token: str, chat_id: str, conn, arg: str) -> None:
        """Handle /removegroup command."""
        if not arg:
            send_telegram_message(bot_token, chat_id, "📝 <b>Usage:</b> /removegroup &lt;id&gt;", parse_mode="HTML")
            return
        
        try:
            gid = int(arg)
            ok = drop_group_table(conn, gid)
            send_telegram_message(bot_token, chat_id, "✅ <b>Group removed.</b>" if ok else "❌ <b>Group not found.</b>", parse_mode="HTML")
        except ValueError:
            send_telegram_message(bot_token, chat_id, "❌ <b>Invalid group ID.</b> Use number.", parse_mode="HTML")
        except Exception as e:
            send_telegram_message(bot_token, chat_id, f"❌ <b>Error:</b> {str(e)}", parse_mode="HTML")
    
    async def _handle_login(self, bot_token: str, chat_id: str, conn) -> None:
        """Handle /login command."""
        login_msg = """🔐 <b>Facebook Login</b>

Choose login method:

• <b>Use Existing Cookies</b> - Check if saved cookies are still valid
• <b>Import Cookies</b> - Import from browser extension (recommended)
• <b>Clear Cookies</b> - Remove existing cookies and start fresh
• <b>Auto Credentials</b> - Requires FB_USER/FB_PASS in .env file

<i>💡 Import Cookies works best for headless servers</i>"""
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "🍪 Use Existing Cookies", "callback_data": "login_existing"}],
                [{"text": "📥 Import Cookies", "callback_data": "login_import"}],
                [{"text": "🧹 Clear Cookies", "callback_data": "login_clear"}],
                [{"text": "📧 Auto Credentials", "callback_data": "login_auto"}]
            ]
        }
        
        self.login_states[chat_id] = 'choosing_login_method'
        send_telegram_message(bot_token, chat_id, login_msg, parse_mode="HTML", reply_markup=keyboard)
    
    async def _handle_login_callback(self, callback_data: str, bot_token: str, chat_id: str, conn, answer_callback) -> None:
        """Handle login-related callback queries."""
        if callback_data == 'login_auto':
            answer_callback("🔑 Using saved credentials...", show_alert=True)
            await self._start_auto_login(bot_token, chat_id)
        elif callback_data == 'login_existing':
            answer_callback("🍪 Checking existing cookies...", show_alert=True)
            await self._use_existing_cookies(bot_token, chat_id)
        elif callback_data == 'login_import':
            answer_callback("📥 Starting cookie import...", show_alert=True)
            await self._start_cookie_import(bot_token, chat_id)
        elif callback_data == 'login_clear':
            answer_callback("🧹 Clearing cookies...", show_alert=True)
            await self._handle_clearcookies(bot_token, chat_id, conn)
    
    async def _start_manual_login(self, bot_token: str, chat_id: str) -> None:
        """Start manual browser login."""
        import threading
        import time
        
        def manual_login_process():
            try:
                manual_driver = create_reliable_webdriver(headless=False)
                manual_driver.get("https://www.facebook.com/")
                logging.info("✅ Manual login browser opened")
                
                # Monitor for login completion
                while True:
                    try:
                        current_url = manual_driver.current_url
                        if "facebook.com" in current_url and "/login" not in current_url:
                            save_cookies(manual_driver, get_cookie_store_path())
                            logging.info("✅ Cookies saved from manual login")
                            break
                        time.sleep(3)
                    except:
                        logging.info("🔒 Manual login browser closed")
                        break
                
                try:
                    manual_driver.quit()
                except:
                    pass
                    
            except Exception as e:
                logging.error(f"Manual login error: {e}")
        
        threading.Thread(target=manual_login_process, daemon=True).start()
    
    async def _start_auto_login(self, bot_token: str, chat_id: str) -> None:
        """Start automatic login with saved credentials."""
        import os
        import threading
        import time
        
        username = os.getenv("FB_USER")
        password = os.getenv("FB_PASS")
        
        if not (username and password):
            send_telegram_message(bot_token, chat_id, "❌ <b>No FB_USER/FB_PASS in .env file</b>\n\nAdd them to your .env file:\n<code>FB_USER=your@email.com\nFB_PASS=yourpassword</code>", parse_mode="HTML")
            return
        
        # Send initial message immediately (not in thread)
        send_telegram_message(bot_token, chat_id, "🔄 <b>Starting automatic login...</b>\n\nThis may take 30-60 seconds...", parse_mode="HTML")
        
        def auto_login_process():
            try:
                # Small delay to ensure the initial message was sent
                time.sleep(2)
                
                logging.info(f"Starting auto login for user: {username}")
                driver = create_reliable_webdriver(headless=True)
                
                if login_to_facebook(driver, username, password):
                    save_cookies(driver, get_cookie_store_path())
                    logging.info("Auto login successful, cookies saved")
                    
                    # Try sending success message with error handling
                    try:
                        send_telegram_message(bot_token, chat_id, "✅ <b>Auto login successful!</b>\n\nCookies saved. You can now start scraping.", parse_mode="HTML")
                    except Exception as msg_error:
                        logging.error(f"Failed to send success message: {msg_error}")
                else:
                    logging.warning("Auto login failed")
                    try:
                        send_telegram_message(bot_token, chat_id, "❌ <b>Auto login failed</b>\n\nPossible issues:\n• Wrong credentials\n• 2FA required\n• Account locked\n• Facebook blocked login\n\nTry manual login instead.", parse_mode="HTML")
                    except Exception as msg_error:
                        logging.error(f"Failed to send failure message: {msg_error}")
                
                driver.quit()
                
            except Exception as e:
                logging.error(f"Auto login process error: {e}")
                try:
                    send_telegram_message(bot_token, chat_id, f"❌ <b>Login error:</b> {str(e)}\n\nTry manual login instead.", parse_mode="HTML")
                except Exception as msg_error:
                    logging.error(f"Failed to send error message: {msg_error}")
        
        # Run in background thread to avoid blocking
        threading.Thread(target=auto_login_process, daemon=True).start()
    
    async def _use_existing_cookies(self, bot_token: str, chat_id: str) -> None:
        """Use existing cookies if available."""
        import threading
        
        def validate_cookies_background():
            try:
                driver = create_reliable_webdriver(headless=True)
                cookie_path = get_cookie_store_path()
                
                if load_cookies(driver, cookie_path):
                    # Send immediate confirmation that cookies exist
                    send_telegram_message(bot_token, chat_id, "✅ <b>Existing cookies are valid!</b>", parse_mode="HTML")
                    
                    # Validate session in background (optional)
                    try:
                        if is_facebook_session_valid(driver):
                            logging.info("✅ Cookie session validation successful")
                        else:
                            logging.warning("⚠️ Cookie session validation failed, but cookies exist")
                    except Exception as validation_error:
                        logging.warning(f"⚠️ Cookie validation timed out: {validation_error}")
                else:
                    send_telegram_message(bot_token, chat_id, "❌ <b>No existing cookies found.</b> Please use another login method.", parse_mode="HTML")
                
                driver.quit()
            except Exception as e:
                send_telegram_message(bot_token, chat_id, f"❌ <b>Cookie validation error:</b> {str(e)}", parse_mode="HTML")
                logging.error(f"Cookie validation error: {e}")
        
        # Run validation in background thread to avoid blocking the bot
        threading.Thread(target=validate_cookies_background, daemon=True).start()
    
    async def _start_cookie_import(self, bot_token: str, chat_id: str) -> None:
        """Start cookie import process with detailed instructions."""
        self.login_states[chat_id] = 'waiting_for_cookies'
        
        instructions = f"""📥 <b>Cookie Import Instructions</b>

<b>Step 1:</b> Install Chrome Extension
• Go to: <a href="https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc">Get cookies.txt LOCALLY</a>
• Click "Add to Chrome"

<b>Step 2:</b> Login to Facebook
• Open facebook.com in Chrome
• Login to your account normally

<b>Step 3:</b> Export Cookies
• Click the extension icon (puzzle piece in toolbar)
• Click "Get cookies.txt LOCALLY"
• Choose "JSON" format
• Click "Export" or "Copy to clipboard"

<b>Step 4:</b> Send Cookies Here
• Copy the JSON text
• Send it as a message in this chat

<b>Alternative formats supported:</b>
• Netscape cookies.txt format
• Raw JSON cookie arrays

<b>⚠️ Security Note:</b>
This extension is open-source and safe. It never sends your data externally.

Send your cookies now:"""
        
        send_telegram_message(bot_token, chat_id, instructions, parse_mode="HTML")
    
    async def _handle_login_flow(self, bot_token: str, chat_id: str, conn, command: str, arg: str) -> None:
        """Handle login flow text responses."""
        state = self.login_states.get(chat_id)
        
        if state == 'waiting_for_cookies':
            await self._process_cookie_import(bot_token, chat_id, arg)
        # Add other login flow states as needed
    
    async def _process_cookie_import(self, bot_token: str, chat_id: str, cookies_text: str) -> None:
        """Process imported cookies with comprehensive format support."""
        try:
            import json
            import os
            
            send_telegram_message(bot_token, chat_id, "🔄 <b>Processing cookies...</b>", parse_mode="HTML")
            
            cookies = []
            
            # Try to parse as JSON first (from extension)
            try:
                cookies_data = json.loads(cookies_text.strip())
                if isinstance(cookies_data, list):
                    cookies = cookies_data
                elif isinstance(cookies_data, dict):
                    cookies = [cookies_data]
                else:
                    raise ValueError("Invalid JSON structure")
                    
                logging.info(f"Parsed {len(cookies)} cookies from JSON format")
                
            except json.JSONDecodeError:
                # Try to parse as Netscape cookies.txt format
                logging.info("JSON parsing failed, trying Netscape format")
                
                for line_num, line in enumerate(cookies_text.strip().split('\n'), 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                        
                    parts = line.split('\t')
                    if len(parts) >= 7:
                        try:
                            cookies.append({
                                'name': parts[5],
                                'value': parts[6],
                                'domain': parts[0],
                                'path': parts[2],
                                'secure': parts[3].lower() == 'true',
                                'httpOnly': False,
                                'sameSite': 'None'
                            })
                        except Exception as e:
                            logging.warning(f"Skipped invalid cookie on line {line_num}: {e}")
                            continue
                
                if cookies:
                    logging.info(f"Parsed {len(cookies)} cookies from Netscape format")
            
            if not cookies:
                error_msg = """❌ <b>No valid cookies found!</b>

<b>Expected formats:</b>
• JSON from "Get cookies.txt LOCALLY" extension
• Netscape cookies.txt format
• Raw JSON cookie arrays

<b>Make sure you:</b>
• Exported from facebook.com (not other sites)
• Used the correct extension
• Copied the complete text

Try again with the correct format."""
                
                send_telegram_message(bot_token, chat_id, error_msg, parse_mode="HTML")
                return
            
            # Filter Facebook cookies only
            fb_cookies = [c for c in cookies if 'facebook.com' in c.get('domain', '')]
            if not fb_cookies:
                send_telegram_message(bot_token, chat_id, "❌ <b>No Facebook cookies found!</b>\n\nMake sure you exported cookies from facebook.com", parse_mode="HTML")
                return
            
            # Save cookies
            cookie_path = get_cookie_store_path()
            os.makedirs(os.path.dirname(cookie_path), exist_ok=True)
            
            with open(cookie_path, 'w') as f:
                json.dump(fb_cookies, f, indent=2)
            
            logging.info(f"Saved {len(fb_cookies)} Facebook cookies to {cookie_path}")
            
            # Test cookies
            send_telegram_message(bot_token, chat_id, "🧪 <b>Testing cookies...</b>", parse_mode="HTML")
            
            driver = create_reliable_webdriver(headless=True)
            if load_cookies(driver, cookie_path) and is_facebook_session_valid(driver):
                success_msg = f"""✅ <b>Cookies imported successfully!</b>

🍪 <b>Imported:</b> {len(cookies)} total cookies
🎯 <b>Facebook:</b> {len(fb_cookies)} Facebook cookies
✅ <b>Status:</b> Session validated

You can now start scraping!"""
                
                send_telegram_message(bot_token, chat_id, success_msg, parse_mode="HTML")
            else:
                send_telegram_message(bot_token, chat_id, "❌ <b>Cookies imported but session is invalid!</b>\n\nPossible issues:\n• Cookies expired\n• Account logged out\n• Wrong account\n\nTry logging in again and re-exporting cookies.", parse_mode="HTML")
            
            driver.quit()
            
            # Clear login state
            if chat_id in self.login_states:
                del self.login_states[chat_id]
                
        except Exception as e:
            error_msg = f"""❌ <b>Cookie import error:</b> {str(e)}

<b>Common issues:</b>
• Invalid format - use the Chrome extension
• Incomplete copy/paste
• Cookies from wrong site

Please try again with the correct format."""
            
            send_telegram_message(bot_token, chat_id, error_msg, parse_mode="HTML")
            logging.error(f"Cookie import error: {e}")
            
            # Clear login state on error
            if chat_id in self.login_states:
                del self.login_states[chat_id]
    
    async def _handle_prompt(self, bot_token: str, chat_id: str, conn) -> None:
        """Handle /prompt command - show current AI prompts."""
        from config import get_bot_runner_settings
        
        # Get default prompts from config
        system_prompt, user_prompt, _, _ = get_bot_runner_settings()
        
        # Get current prompts from database (if set)
        cur_sys = botsettings_get(conn, 'bot_system', system_prompt)
        cur_user = botsettings_get(conn, 'bot_user', user_prompt)
        cur_limit = botsettings_get(conn, 'bot_hourly_limit', '6')
        
        prompt_text = f"""🧠 <b>Current AI Settings:</b>

<b>🔧 System Prompt:</b>
{cur_sys}

<b>👤 User Prompt:</b>
{cur_user}

⚙️ <b>Scraping Settings:</b>
<b>📊 Scrapes per hour:</b> {cur_limit}

<b>Commands:</b>
/setsystem &lt;text&gt; - Change system prompt
/setprompt &lt;text&gt; - Change user prompt"""
        
        send_telegram_message(bot_token, chat_id, prompt_text, parse_mode="HTML")
    
    async def _handle_setsystem(self, bot_token: str, chat_id: str, conn, arg: str) -> None:
        """Handle /setsystem command."""
        if arg:
            botsettings_set(conn, 'bot_system', arg)
            send_telegram_message(bot_token, chat_id, "✅ <b>System prompt updated.</b>", parse_mode="HTML")
        else:
            send_telegram_message(bot_token, chat_id, "📝 <b>Usage:</b> /setsystem &lt;text&gt;", parse_mode="HTML")
    
    async def _handle_setprompt(self, bot_token: str, chat_id: str, conn, arg: str) -> None:
        """Handle /setprompt command."""
        if arg:
            botsettings_set(conn, 'bot_user', arg)
            send_telegram_message(bot_token, chat_id, "✅ <b>User prompt updated.</b>", parse_mode="HTML")
        else:
            send_telegram_message(bot_token, chat_id, "📝 <b>Usage:</b> /setprompt &lt;text&gt;", parse_mode="HTML")

    async def _handle_cookies(self, bot_token: str, chat_id: str, conn) -> None:
        """Handle /cookies command - show cookie status."""
        try:
            import os
            import json
            from datetime import datetime
            
            cookie_path = get_cookie_store_path()
            
            if os.path.exists(cookie_path):
                # Read cookie file to get expiration info
                with open(cookie_path, 'r') as f:
                    cookies = json.load(f)
                
                # Find the earliest expiration date
                earliest_expiry = None
                cookie_count = len(cookies)
                
                for cookie in cookies:
                    if 'expirationDate' in cookie:
                        expiry_timestamp = cookie['expirationDate']
                        expiry_date = datetime.fromtimestamp(expiry_timestamp)
                        if earliest_expiry is None or expiry_date < earliest_expiry:
                            earliest_expiry = expiry_date
                
                # Format expiration date
                expiry_str = earliest_expiry.strftime("%B %d, %Y at %H:%M") if earliest_expiry else "Unknown"
                
                # Send immediate status without blocking validation
                status_msg = f"""🍪 <b>Cookie Status:</b>

📊 <b>Count:</b> {cookie_count} cookies
🔐 <b>Session:</b> 🔄 Validating...
⏰ <b>Expires:</b> {expiry_str}
📁 <b>File:</b> {os.path.basename(cookie_path)}

⏳ <b>Checking session validity...</b>"""
                
                send_telegram_message(bot_token, chat_id, status_msg, parse_mode="HTML")
                
                # Validate session in background thread
                import threading
                
                def validate_session_background():
                    try:
                        driver = create_reliable_webdriver(headless=True)
                        cookies_loaded = load_cookies(driver, cookie_path)
                        session_valid = False
                        
                        if cookies_loaded:
                            session_valid = is_facebook_session_valid(driver)
                        
                        driver.quit()
                        
                        # Send updated status
                        final_msg = f"""🍪 <b>Cookie Status - Updated:</b>

📊 <b>Count:</b> {cookie_count} cookies
🔐 <b>Session:</b> {'✅ Active' if session_valid else '❌ Invalid'}
⏰ <b>Expires:</b> {expiry_str}
📁 <b>File:</b> {os.path.basename(cookie_path)}

{'✅ <b>All good!</b> Cookies are working.' if session_valid else '❌ <b>Session expired!</b> Use /login to refresh.'}"""
                        
                        send_telegram_message(bot_token, chat_id, final_msg, parse_mode="HTML")
                        
                    except Exception as e:
                        error_msg = f"🍪 <b>Cookie Status - Error:</b>\n\n❌ <b>Validation failed:</b> {str(e)}"
                        send_telegram_message(bot_token, chat_id, error_msg, parse_mode="HTML")
                        logging.error(f"Background cookie validation error: {e}")
                
                threading.Thread(target=validate_session_background, daemon=True).start()
            else:
                send_telegram_message(bot_token, chat_id, "❌ <b>No cookies found.</b>\n\nUse /login to authenticate with Facebook.", parse_mode="HTML")
                
        except Exception as e:
            send_telegram_message(bot_token, chat_id, f"❌ <b>Error checking cookies:</b> {str(e)}", parse_mode="HTML")
            logging.error(f"Error checking cookie status: {e}")

    async def _handle_clearcookies(self, bot_token: str, chat_id: str, conn) -> None:
        """Handle /clearcookies command - clear all cookies."""
        try:
            import os
            cookie_path = get_cookie_store_path()
            
            if os.path.exists(cookie_path):
                send_telegram_message(bot_token, chat_id, "🧹 <b>Clearing cookies...</b>", parse_mode="HTML")
                os.remove(cookie_path)
                logging.info(f"Cleared cookies from {cookie_path}")
                send_telegram_message(bot_token, chat_id, "✅ <b>Cookies cleared successfully!</b>\n\nUse /login to authenticate again.", parse_mode="HTML")
            else:
                send_telegram_message(bot_token, chat_id, "❌ <b>No cookies to clear.</b>", parse_mode="HTML")
                
        except Exception as e:
            send_telegram_message(bot_token, chat_id, f"❌ <b>Error clearing cookies:</b> {str(e)}", parse_mode="HTML")
            logging.error(f"Error clearing cookies: {e}")