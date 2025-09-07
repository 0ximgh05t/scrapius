#!/usr/bin/env python3
"""
Clean Telegram Bot Implementation for Scrapius
Replaces the monolithic main.py approach with proper architecture.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from notifier.telegram_notifier import get_updates, extract_commands, send_telegram_message
from database.crud import get_db_connection, botsettings_get, botsettings_set
from database.simple_per_group import list_all_groups
from config import (
    get_telegram_settings, get_bot_runner_settings, get_hourly_limit_defaults,
    is_within_working_hours, get_next_working_time, get_reliability_settings
)
from bot.scraper_manager import ScraperManager
from bot.command_handlers import CommandHandlers


class ScrapiusTelegramBot:
    """
    Clean, modular Telegram bot for Scrapius.
    Handles all bot operations with proper separation of concerns.
    """
    
    def __init__(self):
        self.bot_token: Optional[str] = None
        self.chat_ids: List[str] = []
        self.last_update_id: int = 0
        self.hourly_limit: int = 6
        self.schedule_times: List[datetime] = []
        
        # Initialize components
        self.command_handlers = CommandHandlers()
        self.scraper_manager = ScraperManager(self.command_handlers)
        
        # Throttle working hours logging - only log every 10 minutes
        self.last_working_hours_log = datetime.min.replace(tzinfo=timezone.utc)
        
        logging.info("🤖 Scrapius Telegram Bot initialized")
    
    def initialize(self) -> bool:
        """Initialize bot configuration and validate settings."""
        try:
            # Get Telegram settings
            self.bot_token, self.chat_ids = get_telegram_settings()
            if not (self.bot_token and self.chat_ids):
                logging.error("❌ Telegram not configured. Set TELEGRAM_BOT_TOKEN and ALLOWED_CHAT_IDS in .env.")
                return False
            
            # Get hourly limit
            self.hourly_limit = get_hourly_limit_defaults()
            
            # Initialize database connection and get last update ID
            conn = get_db_connection()
            if not conn:
                logging.error("❌ Could not connect to database")
                return False
            
            try:
                self.last_update_id = int(botsettings_get(conn, 'last_update_id', '0'))
            except Exception:
                self.last_update_id = 0
            
            conn.close()
            
            logging.info(f"🔧 Allowed chat IDs: {self.chat_ids}")
            logging.info(f"🤖 Bot token length: {len(self.bot_token)}")
            
            return True
            
        except Exception as e:
            logging.error(f"❌ Bot initialization failed: {e}")
            return False
    
    def next_scheduled_times(self, now: datetime, limit: int) -> List[datetime]:
        """Return scheduled times spread across the next hour with jitter."""
        import random
        
        limit = max(1, limit)
        slot_len = 60.0 / limit
        times = []
        
        # Start from the next slot, not immediately
        for i in range(limit):
            start = (i + 1) * slot_len  # +1 to avoid immediate execution
            jitter = random.uniform(0, min(5, slot_len * 0.1))  # Small jitter only
            times.append(now + timedelta(minutes=start + jitter))
        return times
    
    async def handle_telegram_updates(self, conn) -> None:
        """Handle incoming Telegram messages and commands."""
        try:
            # Get Telegram updates with short timeout for responsiveness
            offset = self.last_update_id + 1 if self.last_update_id else None
            updates = get_updates(self.bot_token, offset=offset, timeout=2)
            
            if not updates.get('ok') or not updates.get('result'):
                return
            
            for upd in updates['result']:
                self.last_update_id = upd['update_id']
                
                # Handle callback queries (button clicks)
                if 'callback_query' in upd:
                    await self.command_handlers.handle_callback_query(upd, self.bot_token, self.chat_ids, conn)
                    continue
                
                # Handle text messages
                if 'message' in upd and 'text' in upd['message']:
                    msg = upd['message']
                    chat_id = str(msg.get('chat', {}).get('id', ''))
                    text = msg.get('text', '')
                    
                    # Allow commands from any chat (removed restriction)
                    # if chat_id not in self.chat_ids:
                    #     continue
                    
                    # Handle regular commands (starting with /) - ALWAYS check commands first
                    cmd = extract_commands(upd)
                    if cmd:
                        await self.command_handlers.handle_text_command(cmd, self.bot_token, conn)
                    elif chat_id in self.command_handlers.login_states:
                        # Process as login flow message (cookies, credentials, etc.) only if not a command
                        await self.command_handlers._handle_login_flow(self.bot_token, chat_id, conn, '', text)
            
            # Save last update ID
            botsettings_set(conn, 'last_update_id', str(self.last_update_id))
            
        except Exception as e:
            logging.error(f"❌ ERROR in handle_telegram_updates: {e}")
            import traceback
            logging.error(f"Full traceback: {traceback.format_exc()}")
            # Don't let Telegram API errors block the main loop - wait longer on network errors
            if "Connection" in str(e) or "timeout" in str(e).lower():
                logging.warning("⚠️ Network connectivity issue - waiting 5s before retry")
                await asyncio.sleep(5)
            else:
                await asyncio.sleep(0.1)
    
    async def should_run_scrape_cycle(self, conn) -> bool:
        """Check if it's time to run a scrape cycle."""
        # Check if manual login is in progress
        if hasattr(self.command_handlers, '_pause_main_scraper') and self.command_handlers._pause_main_scraper:
            return False
            
        # Check working hours
        if not is_within_working_hours(conn):
            # Only log this message every 10 minutes to avoid spam
            now = datetime.now(timezone.utc)
            if now - self.last_working_hours_log > timedelta(minutes=10):
                next_working = get_next_working_time(conn)
                logging.info(f"⏰ Outside working hours - bot paused. {next_working}")
                self.last_working_hours_log = now
            return False
        
        # Check hourly limit schedule
        now = datetime.now(timezone.utc)
        
        # Refresh limit from DB if changed externally
        old_hourly_limit = self.hourly_limit
        try:
            new_limit = int(botsettings_get(conn, 'bot_hourly_limit', str(self.hourly_limit)))
            self.hourly_limit = new_limit
        except Exception:
            pass
        
        # Regenerate schedule if limit changed
        if self.hourly_limit != old_hourly_limit:
            logging.info(f"📊 Hourly limit changed from {old_hourly_limit} to {self.hourly_limit} - regenerating schedule")
            self.schedule_times = self.next_scheduled_times(now, self.hourly_limit)
        
        if not self.schedule_times or now >= self.schedule_times[0]:
            if self.schedule_times:
                self.schedule_times.pop(0)
            else:
                self.schedule_times = self.next_scheduled_times(now, self.hourly_limit)
            return True
        
        return False
    
    async def run_scrape_cycle(self, conn) -> None:
        """Run a complete scrape cycle for all groups."""
        try:
            # Get groups and reliability settings
            groups_rows = list_all_groups(conn)
            reliability = get_reliability_settings(conn)
            
            # Check if there are any groups to scrape
            if not groups_rows:
                logging.info("📭 No groups configured for scraping")
                return
            
            logging.info(f"🎯 Found {len(groups_rows)} groups to scrape")
            
            # Initialize scraper manager
            if not await self.scraper_manager.initialize():
                logging.error("❌ Failed to initialize scraper")
                return
            
            # Process each group
            for group_index, group_data in enumerate(groups_rows):
                try:
                    # Check for Telegram updates before each group
                    await self.handle_telegram_updates(conn)
                    
                    await self.scraper_manager.scrape_group(
                        group_data, group_index, len(groups_rows), 
                        reliability, conn, self.bot_token, self.chat_ids
                    )
                    
                    # Add delay between groups with async sleep for responsiveness
                    if group_index < len(groups_rows) - 1:
                        group_delay = reliability['group_delay']
                        logging.info(f"⏳ Waiting {group_delay}s before next group (reliability)")
                        await asyncio.sleep(group_delay)
                        
                except Exception as e:
                    logging.error(f"❌ Error scraping group {group_data.get('group_url', 'unknown')}: {e}")
                    continue
            
        except Exception as e:
            logging.error(f"❌ Error in scrape cycle: {e}")
        finally:
            await self.scraper_manager.cleanup()
    
    async def run(self) -> None:
        """Main bot loop."""
        if not self.initialize():
            return
        
        # Initialize schedule
        self.schedule_times = self.next_scheduled_times(datetime.now(timezone.utc), self.hourly_limit)
        
        logging.info("🚀 Scrapius bot started - entering main loop")
        
        loop_count = 0
        try:
            while True:
                loop_count += 1
                # Heartbeat every 600 loops (roughly every 60 seconds)
                if loop_count % 600 == 0:
                    logging.info(f"💓 Bot heartbeat - loop {loop_count} - responsive and running")
                conn = get_db_connection()
                if not conn:
                    logging.error("❌ Could not connect to database in main loop")
                    await asyncio.sleep(60)
                    continue
                
                try:
                    # Handle Telegram updates (check frequently)
                    await self.handle_telegram_updates(conn)
                    
                    # Check if should run scrape cycle
                    if await self.should_run_scrape_cycle(conn):
                        await self.run_scrape_cycle(conn)
                    
                    # Very short delay for maximum responsiveness during manual login
                    await asyncio.sleep(0.1)
                    
                finally:
                    conn.close()
                    
        except KeyboardInterrupt:
            logging.info("🛑 Bot stopped by user")
        except Exception as e:
            logging.error(f"❌ Fatal error in bot main loop: {e}")
        finally:
            await self.scraper_manager.cleanup()


async def main():
    """Main entry point."""
    bot = ScrapiusTelegramBot()
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main()) 