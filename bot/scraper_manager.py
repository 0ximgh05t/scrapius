#!/usr/bin/env python3
"""
Scraper Manager for Scrapius Bot
Handles all Facebook scraping operations with proper error handling and reliability.
"""

import asyncio
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
    
    def __init__(self, command_handlers=None):
        self.driver = None
        self.initialized = False
        self.command_handlers = command_handlers
    
    async def initialize(self) -> bool:
        """Initialize the scraper with WebDriver and session."""
        try:
            if self.initialized and self.driver:
                # Check if existing browser is still alive
                try:
                    self.driver.current_url  # Quick test
                    logging.info("🔄 Reusing existing browser session")
                    return True
                except:
                    logging.info("🔄 Browser died, creating new one")
                    self.initialized = False
            
            logging.info("🆕 Creating browser for scraping")
            
            # Create a unique user data directory for scraper to avoid conflicts with manual login
            import tempfile
            import os
            scraper_profile_dir = os.path.join(tempfile.gettempdir(), f"scrapius_scraper_{os.getpid()}")
            os.makedirs(scraper_profile_dir, exist_ok=True)
            
            # Set environment variable to force unique profile
            os.environ['CHROME_USER_DATA_DIR'] = scraper_profile_dir
            os.environ['CHROME_PROFILE_DIR'] = 'ScrapiusScraper'
            
            self.driver = create_reliable_webdriver(headless=True)
            self.reused_manual_browser = False
                
            if not self.driver:
                logging.error("❌ Failed to create WebDriver")
                return False
            
            # Load cookies
            cookie_path = get_cookie_store_path()
            logging.info(f"🍪 Attempting to load cookies from: {cookie_path}")
            
            if os.path.exists(cookie_path):
                logging.info("🍪 Cookie file exists - loading...")
                if load_cookies(self.driver, cookie_path):
                    logging.info("✅ Cookies loaded successfully")
                else:
                    logging.warning("⚠️ Failed to load cookies - may be invalid")
            else:
                logging.warning("⚠️ No cookie file found - need fresh login")
            
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
            # SUPER SIMPLE CHECK: Get most recent Facebook post ID from database
            from database.simple_per_group import get_most_recent_facebook_post_id, get_most_recent_post_content_hash
            most_recent_fb_id = get_most_recent_facebook_post_id(conn, table_name)
            most_recent_hash = get_most_recent_post_content_hash(conn, table_name)
            
            # Quick check: if we can get the first post ID from Facebook and it matches database, skip entirely
            if most_recent_fb_id:
                logging.info(f"🔍 Most recent post in database: {most_recent_fb_id}")
                # TODO: Add quick Facebook first post check here
            
            # Scrape posts with reliability settings - NO AUTHOR per user decision
            # Pass database connection and most recent hash for proper incremental scraping
            posts = list(scrape_authenticated_group(
                self.driver,
                group_url,
                num_posts=reliability['max_posts_per_group'],
                fields_to_scrape=["content_text", "post_image_url"],
                stop_at_url=None,
                skip_virtual_display=False,
                db_conn=conn,
                most_recent_hash=most_recent_hash
            ))
            
            if not posts:
                logging.info(f"📭 No new posts found in group {group_url}")
                return
            
            logging.info(f"📊 Found {len(posts)} new posts in group {group_url}")
            
            # NEW ARCHITECTURE: Process all posts first, then send notifications
            await self._process_posts_batch(
                posts, group_id, table_name, conn, 
                bot_token, chat_ids, reliability
            )
            
        except Exception as e:
            logging.error(f"❌ Error scraping group {group_url}: {e}")
            raise
    
    async def _process_posts_batch(
        self,
        posts: List[Dict],
        group_id: int,
        table_name: str,
        conn,
        bot_token: str,
        chat_ids: List[str],
        reliability: Dict
    ) -> None:
        """Process all posts in batch: save to DB first, then send notifications in order."""
        if not posts:
            return
            
        logging.info(f"🔄 Processing {len(posts)} posts in batch mode")
        
        # STEP 1: Process all posts and collect results (no notifications yet)
        processed_results = []
        
        for post_index, post in enumerate(posts):
            try:
                # Extract post data
                content = post.get('content_text', '')
                post_url = post.get('post_url', '')
                content_hash = post.get('content_hash', '')
                
                if not content or not content_hash:
                    logging.warning(f"⚠️ Skipping post {post_index + 1} with missing content or hash")
                    continue
                
                # Check for duplicates BEFORE AI processing
                from database.simple_per_group import content_hash_exists
                if content_hash_exists(conn, table_name, content_hash):
                    logging.info(f"🔄 Skipping duplicate post {post_index + 1} (hash: {content_hash[:12]}...)")
                    continue
                
                # AI Processing
                ai_result = None
                try:
                    ai_result = decide_and_summarize_for_post(content)
                    if ai_result:
                        logging.info(f"🤖 AI processed post {post_index + 1}: {ai_result.get('relevant', False)}")
                    else:
                        logging.warning(f"⚠️ AI processing failed for post {post_index + 1}")
                        continue
                except Exception as e:
                    logging.error(f"❌ AI processing error for post {post_index + 1}: {e}")
                    continue
                
                # Only process relevant posts
                if not ai_result.get('relevant', False):
                    logging.info(f"🚫 Post {post_index + 1} not relevant - skipping")
                    continue
                
                # Prepare post data for database
                post_data_dict = {
                    'facebook_post_id': post.get('facebook_post_id'),
                    'post_url': post_url,
                    'content_text': content,
                    'content_hash': content_hash
                }
                
                # Store for batch processing
                processed_results.append({
                    'post_data': post_data_dict,
                    'content': content,
                    'post_url': post_url,
                    'ai_result': ai_result,
                    'post_index': post_index + 1
                })
                
                logging.info(f"✅ Post {post_index + 1} prepared for database insertion")
                
            except Exception as e:
                logging.error(f"❌ Error preparing post {post_index + 1}: {e}")
                continue
        
        if not processed_results:
            logging.info("📭 No relevant posts to save after processing")
            return
        
        # STEP 2: Save all posts to database in batch
        logging.info(f"💾 Saving {len(processed_results)} posts to database...")
        saved_posts = []
        
        for result in processed_results:
            try:
                from database.simple_per_group import add_post_to_group
                db_result = add_post_to_group(conn, table_name, result['post_data'])
                
                if db_result and db_result[1]:  # Successfully saved (new post, not update)
                    saved_posts.append({
                        'internal_post_id': db_result[0],
                        'content': result['content'],
                        'post_url': result['post_url'],
                        'ai_result': result['ai_result'],
                        'post_index': result['post_index']
                    })
                    logging.info(f"✅ Saved post {result['post_index']} to database with ID {db_result[0]}")
                else:
                    logging.info(f"📝 Post {result['post_index']} already exists in database - skipping notification")
                    
            except Exception as e:
                logging.error(f"❌ Error saving post {result['post_index']} to database: {e}")
                continue
        
        # STEP 3: Send notifications for saved posts in correct order
        if saved_posts:
            logging.info(f"📱 Sending {len(saved_posts)} notifications in chronological order...")
            
            for saved_post in saved_posts:
                try:
                    await self._send_post_notification(
                        saved_post['content'],
                        'Anonymous',  # No author stored in database
                        saved_post['post_url'],
                        saved_post['ai_result'],
                        bot_token,
                        chat_ids
                    )
                    
                    logging.info(f"📱 Notification sent for post ID {saved_post['internal_post_id']}")
                    
                    # Add delay between notifications
                    await asyncio.sleep(reliability['post_processing_delay'])
                    
                except Exception as e:
                    logging.error(f"❌ Error sending notification for post ID {saved_post['internal_post_id']}: {e}")
                    continue
        
        logging.info(f"🎉 Batch processing complete: {len(saved_posts)} posts saved and notified")
    
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
            
            # CHECK FOR DUPLICATES BEFORE AI PROCESSING (save API costs)
            from database.simple_per_group import content_hash_exists
            if content_hash_exists(conn, table_name, content_hash):
                logging.info(f"🔄 Skipping duplicate post (hash: {content_hash[:12]}...)")
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
            result = add_post_to_group(conn, table_name, post_data_dict)
            
            # Send notification ONLY if post was actually saved (not duplicate) and relevant
            if result and result[1] and ai_result and ai_result.get('relevant', False):
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
            
            # Get actual group name from database using post URL
            group_name = "Unknown Group"
            try:
                # Extract group URL from post URL to find the correct group
                if 'facebook.com/groups/' in post_url:
                    # Extract group identifier from post URL
                    import re
                    group_match = re.search(r'facebook\.com/groups/([^/]+)', post_url)
                    if group_match:
                        group_identifier = group_match.group(1)
                        cursor = conn.cursor()
                        # Try exact URL match first, then partial match
                        cursor.execute("SELECT group_name FROM Groups WHERE group_url = ? OR group_url LIKE ?", 
                                     (f'https://www.facebook.com/groups/{group_identifier}', f'%{group_identifier}%'))
                        result = cursor.fetchone()
                        if result:
                            raw_group_name = result[0]
                            # Clean up the group name for display
                            if raw_group_name.startswith("Group from "):
                                # Extract just the group identifier from the fallback name
                                group_name = group_identifier
                            else:
                                group_name = raw_group_name
                            logging.debug(f"Found group name: {group_name}")
                        else:
                            logging.debug(f"No group found for identifier: {group_identifier}")
                
                # Fallback: use current group name if available
                if group_name == "Unknown Group" and hasattr(self, '_current_group_name'):
                    group_name = self._current_group_name
                    
            except Exception as e:
                logging.debug(f"Could not get group name: {e}")
            
            conn.close()
            
            # Format notification message using Lithuanian format
            title = "Naujas įrašas"
            # Use actual post content, not AI summary (limit to 300 chars and clean up)
            clean_content = content.replace('See more', '').replace('Show more', '').strip()
            short_text = clean_content[:300] + '...' if len(clean_content) > 300 else clean_content
            
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