#!/usr/bin/env python3
"""
Smart reprocessing script for today's unprocessed posts.
Processes from oldest to newest with proper delays.
"""

import sqlite3
import asyncio
import logging
from datetime import datetime
from typing import List, Dict
import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.crud import get_db_connection, botsettings_get
from config import get_bot_runner_settings
from ai.openai_service import decide_and_summarize_for_post
from database.simple_per_group import update_ai_result

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def get_all_posts_today() -> List[Dict]:
    """Get ALL posts from today, ordered by scraped_at (oldest first)."""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        
        # Get all table names for groups
        cursor.execute("SELECT table_name FROM Groups ORDER BY group_id")
        table_names = [row[0] for row in cursor.fetchall()]
        
        all_posts = []
        
        for table_name in table_names:
            posts_table = f"Posts_{table_name}"
            
            # Get ALL posts from today for this group (regardless of AI status)
            cursor.execute(f"""
                SELECT 
                    internal_post_id,
                    post_content_raw,
                    post_url,
                    scraped_at,
                    '{table_name}' as table_suffix
                FROM {posts_table}
                WHERE DATE(scraped_at) = DATE('now')
                ORDER BY scraped_at ASC
            """)
            
            group_posts = cursor.fetchall()
            for post in group_posts:
                all_posts.append({
                    'internal_post_id': post[0],
                    'content_text': post[1],
                    'post_url': post[2],
                    'scraped_at': post[3],
                    'table_suffix': post[4]
                })
        
        # Sort all posts by scraped_at (oldest first)
        all_posts.sort(key=lambda x: x['scraped_at'])
        
        logging.info(f"📋 Found {len(all_posts)} posts from today (will reprocess all)")
        return all_posts
        
    except Exception as e:
        logging.error(f"❌ Error getting unprocessed posts: {e}")
        return []
    finally:
        conn.close()

async def reprocess_posts_smart():
    """Smart reprocessing with delays and progress tracking."""
    
    # Get all posts from today
    posts = get_all_posts_today()
    if not posts:
        logging.info("✅ No posts found from today!")
        return
    
    # Get AI prompts
    conn = get_db_connection()
    if not conn:
        logging.error("❌ Cannot connect to database")
        return
    
    try:
        # Get prompts
        default_system, default_user, _, _ = get_bot_runner_settings()
        system_prompt = botsettings_get(conn, 'bot_system', default_system)
        user_prompt = botsettings_get(conn, 'bot_user', default_user)
        
        logging.info(f"🚀 Starting smart reprocessing of {len(posts)} posts...")
        logging.info(f"⏱️ Estimated time: {len(posts) * 2} seconds (2s delay per post)")
        
        processed_count = 0
        relevant_count = 0
        error_count = 0
        
        for i, post in enumerate(posts, 1):
            try:
                # Show progress with content glimpse
                content_preview = post['content_text'][:150].replace('\n', ' ').strip()
                if len(post['content_text']) > 150:
                    content_preview += "..."
                
                logging.info(f"🔄 [{i}/{len(posts)}] Processing post ID {post['internal_post_id']} from {post['scraped_at']}")
                logging.info(f"   📝 Content ({len(post['content_text'])} chars): \"{content_preview}\"")
                
                # Create post dict for AI - USE FULL CONTENT!
                post_dict = {
                    'content': post['content_text'],  # FULL content, no truncation!
                    'author': 'Anonymous',
                    'url': post['post_url']
                }
                
                # AI processing
                is_relevant, summary = decide_and_summarize_for_post(
                    post_dict, 
                    system_prompt,
                    user_prompt
                )
                
                # Update database
                success = update_ai_result(
                    conn, 
                    post['table_suffix'], 
                    post['internal_post_id'], 
                    is_relevant, 
                    summary
                )
                
                if success:
                    processed_count += 1
                    if is_relevant:
                        relevant_count += 1
                    
                    status = "✅ RELEVANT" if is_relevant else "⚪ Not relevant"
                    logging.info(f"   {status} - Updated database successfully")
                else:
                    error_count += 1
                    logging.error(f"   ❌ Failed to update database")
                
                # Smart delay - 2 seconds between posts to avoid rate limits
                if i < len(posts):  # Don't delay after the last post
                    await asyncio.sleep(2.0)
                
            except Exception as e:
                error_count += 1
                logging.error(f"   ❌ Error processing post {post['internal_post_id']}: {e}")
                # Continue with next post
                await asyncio.sleep(1.0)  # Shorter delay on error
        
        # Final summary
        logging.info("=" * 60)
        logging.info("🎉 REPROCESSING COMPLETE!")
        logging.info(f"📊 Processed: {processed_count}/{len(posts)}")
        logging.info(f"✅ Relevant: {relevant_count}")
        logging.info(f"⚪ Not relevant: {processed_count - relevant_count}")
        logging.info(f"❌ Errors: {error_count}")
        logging.info("=" * 60)
        
        if relevant_count > 0:
            logging.info(f"🎯 Found {relevant_count} relevant posts that should now trigger notifications!")
        
    except Exception as e:
        logging.error(f"❌ Fatal error during reprocessing: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    print("🤖 Smart Post Reprocessing Tool")
    print("=" * 50)
    print("This will reprocess ALL posts from today (including previously processed ones)")
    print("Processing order: Oldest to newest")
    print("Delay: 2 seconds between posts")
    print("=" * 50)
    
    confirm = input("Continue? (y/N): ").strip().lower()
    if confirm != 'y':
        print("❌ Cancelled")
        sys.exit(0)
    
    # Run the reprocessing
    asyncio.run(reprocess_posts_smart()) 