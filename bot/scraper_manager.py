#!/usr/bin/env python3
"""
Scraper Manager for Scrapius Bot
Handles all Facebook scraping operations with proper error handling and reliability.
"""

import logging
import time
from typing import Dict, List, Optional, Any

from config import create_reliable_webdriver, get_cookie_store_path
from scraper.facebook_scraper_headless import scrape_authenticated_group, is_facebook_session_valid
from scraper.session_persistence import load_cookies, save_cookies
# Import database functions when needed to avoid early Selenium imports
from notifier.telegram_notifier import send_telegram_message, format_post_message
from ai.openai_service import decide_and_summarize_for_post


class ScraperManager:
    """
    Manages Facebook scraping operations with proper resource management.
    """
    
    def __init__(self):
        self.driver = None
        self.initialized = False
    
    async def initialize(self) -> bool:
        """Initialize the scraper with WebDriver and session."""
        try:
            if self.initialized:
                return True
            
            # Create WebDriver
            self.driver = create_reliable_webdriver(headless=True)
            if not self.driver:
                logging.error("❌ Failed to create WebDriver")
                return False
            
            # Load cookies
            cookie_path = get_cookie_store_path()
            if not load_cookies(self.driver, cookie_path):
                logging.warning("⚠️ No valid cookies found - may need login")
            
            # Validate session
            if not is_facebook_session_valid(self.driver):
                logging.error("❌ Facebook session invalid - need to login")
                return False
            
            self.initialized = True
            logging.info("✅ Scraper manager initialized successfully")
            return True
            
        except Exception as e:
            logging.error(f"❌ Failed to initialize scraper: {e}")
            await self.cleanup()
            return False
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
            self.initialized = False
            logging.info("🧹 Scraper manager cleaned up")
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")
    
    async def scrape_group(
        self, 
        group_data: Dict, 
        group_index: int, 
        total_groups: int,
        reliability: Dict,
        conn,
        bot_token: str,
        chat_ids: List[str]
    ) -> None:
        """Scrape a single Facebook group."""
        group_url = group_data['group_url']
        group_id = group_data['group_id']
        table_name = group_data['table_name']
        
        # Store current group name for notifications
        self._current_group_name = group_data.get('group_name', 'Unknown Group')
        
        logging.info(f"🔍 [{group_index + 1}/{total_groups}] Scraping group: {group_url}")
        
        try:
            # Get most recent post hash for incremental scraping
            from database.simple_per_group import get_most_recent_post_content_hash
            most_recent_hash = get_most_recent_post_content_hash(conn, table_name)
            
            # Scrape posts with reliability settings - NO AUTHOR per user decision
            posts = list(scrape_authenticated_group(
                self.driver,
                group_url,
                num_posts=reliability['max_posts_per_group'],
                fields_to_scrape=["content_text", "post_image_url"]
            ))
            
            if not posts:
                logging.info(f"📭 No new posts found in group {group_url}")
                return
            
            logging.info(f"📊 Found {len(posts)} new posts in group {group_url}")
            
            # Process each post
            for post_index, post in enumerate(posts):
                try:
                    await self._process_single_post(
                        post, group_id, table_name, conn, 
                        bot_token, chat_ids, reliability
                    )
                    
                    # Add delay between posts
                    if post_index < len(posts) - 1:
                        time.sleep(reliability['post_processing_delay'])
                        
                except Exception as e:
                    logging.error(f"❌ Error processing post {post_index + 1}: {e}")
                    continue
            
        except Exception as e:
            logging.error(f"❌ Error scraping group {group_url}: {e}")
            raise
    
    async def _process_single_post(
        self,
        post: Dict,
        group_id: int,
        table_name: str,
        conn,
        bot_token: str,
        chat_ids: List[str],
        reliability: Dict
    ) -> None:
        """Process a single post with AI filtering and notifications."""
        try:
            # Extract post data using ACTUAL field names from scraper - NO AUTHOR
            content = post.get('content_text', '')
            author = 'Anonymous'  # No author scraping per user decision
            post_url = post.get('post_url', '')
            content_hash = post.get('content_hash', '')
            
            if not content or not content_hash:
                logging.warning("⚠️ Skipping post with missing content or hash")
                return
            
            # AI Processing
            ai_result = None
            try:
                # Get AI prompts from database or config
                from config import get_bot_runner_settings
                from database.crud import botsettings_get
                
                # Get default prompts
                default_system, default_user, _, _ = get_bot_runner_settings()
                
                # Get current prompts from database (if set)
                system_prompt = botsettings_get(conn, 'bot_system', default_system)
                user_prompt = botsettings_get(conn, 'bot_user', default_user)
                
                # Create post dict for AI processing
                post_dict = {'content': content, 'author': author, 'url': post_url}
                is_relevant, summary = decide_and_summarize_for_post(
                    post_dict, 
                    system_prompt,
                    user_prompt
                )
                ai_result = {
                    'relevant': is_relevant,
                    'summary': summary,
                    'title': "Relevant Post"  # No author in title
                }
                logging.info(f"🤖 AI processed post: {is_relevant}")
            except Exception as e:
                logging.error(f"❌ AI processing failed: {e}")
                # Continue without AI - still save the post
            
            # Save to database
            from database.simple_per_group import add_post_to_group
            post_data_dict = {
                'content_text': content,
                'post_url': post_url,
                'content_hash': content_hash,
                'ai_result': ai_result
                # NO AUTHOR - per user requirement
            }
            add_post_to_group(conn, table_name, post_data_dict)
            
            # Send notification if relevant
            if ai_result and ai_result.get('relevant', False):
                await self._send_post_notification(
                    content, author, post_url, ai_result,
                    bot_token, chat_ids
                )
            
        except Exception as e:
            logging.error(f"❌ Error processing single post: {e}")
            raise
    
    async def _send_post_notification(
        self,
        content: str,
        author: str,
        post_url: str,
        ai_result: Dict,
        bot_token: str,
        chat_ids: List[str]
    ) -> None:
        """Send Telegram notification for relevant post."""
        try:
            # Get group name from database
            from database.crud import get_db_connection
            conn = get_db_connection()
            
            # Extract group info from current scraping context
            group_name = "Unknown Group"
            try:
                # Get group name from the current context (this is a bit hacky but works)
                # We could pass group_id as parameter, but for now we'll extract from URL
                if hasattr(self, '_current_group_name'):
                    group_name = self._current_group_name
                else:
                    # Fallback: try to get from database if we have the URL
                    cursor = conn.cursor()
                    cursor.execute("SELECT group_name FROM Groups LIMIT 1")  # Get any group for now
                    result = cursor.fetchone()
                    if result:
                        group_name = result[0]
            except Exception as e:
                logging.debug(f"Could not get group name: {e}")
            
            conn.close()
            
            # Format notification message using Lithuanian format
            title = "Naujas įrašas"
            # Use actual post content, not AI summary
            short_text = content[:500] + '...' if len(content) > 500 else content
            
            message = format_post_message(title, short_text, post_url, author, group_name)
            
            # Send only to group chats (negative IDs), skip personal chats (positive IDs)
            group_chats = [chat_id for chat_id in chat_ids if chat_id.startswith('-')]
            
            if not group_chats:
                logging.info("📱 No group chats configured for notifications")
                return
                
            for chat_id in group_chats:
                try:
                    success = send_telegram_message(bot_token, chat_id, message, parse_mode="HTML")
                    if success:
                        logging.info(f"📱 Notification sent to group {chat_id}")
                    else:
                        logging.warning(f"⚠️ Failed to send notification to group {chat_id}")
                except Exception as e:
                    logging.error(f"❌ Error sending to group {chat_id}: {e}")
                    continue
            
        except Exception as e:
            logging.error(f"❌ Error sending notification: {e}")
    
    async def validate_session(self) -> bool:
        """Validate current Facebook session."""
        try:
            if not self.initialized or not self.driver:
                return False
            
            return is_facebook_session_valid(self.driver)
            
        except Exception as e:
            logging.error(f"❌ Error validating session: {e}")
            return False
    
    async def refresh_session(self) -> bool:
        """Refresh Facebook session by reloading cookies."""
        try:
            if not self.driver:
                return False
            
            cookie_path = get_cookie_store_path()
            if load_cookies(self.driver, cookie_path):
                logging.info("🔄 Session refreshed from cookies")
                return True
            else:
                logging.warning("⚠️ Failed to refresh session - no valid cookies")
                return False
                
        except Exception as e:
            logging.error(f"❌ Error refreshing session: {e}")
            return False 