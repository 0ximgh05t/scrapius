#!/usr/bin/env python3
"""
Scrapius - Clean Main Entry Point
Uses proper modular architecture instead of monolithic approach.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from bot.telegram_bot import ScrapiusTelegramBot
from database.db_setup import init_db


def setup_logging():
    """Configure logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('scrapius.log', encoding='utf-8')
        ]
    )


def check_environment():
    """Check if all required environment variables are set."""
    required_vars = [
        'TELEGRAM_BOT_TOKEN',
        'ALLOWED_CHAT_IDS',
        'OPENAI_API_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease set these in your .env file or environment.")
        return False
    
    return True


async def main():
    """Main entry point for Scrapius bot."""
    print("🤖 Starting Scrapius - Clean Architecture Version")
    
    # Setup logging
    setup_logging()
    
    # Check environment
    if not check_environment():
        return 1
    
    # Initialize database
    try:
        init_db()
        logging.info("✅ Database initialized")
    except Exception as e:
        logging.error(f"❌ Database initialization failed: {e}")
        return 1
    
    # Create and run bot
    try:
        bot = ScrapiusTelegramBot()
        await bot.run()
        return 0
    except KeyboardInterrupt:
        logging.info("🛑 Bot stopped by user")
        return 0
    except Exception as e:
        logging.error(f"❌ Fatal error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 