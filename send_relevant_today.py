#!/usr/bin/env python3
"""
Send only today's RELEVANT posts to Telegram.
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

from database.crud import get_db_connection
from notifier.telegram_notifier import send_telegram_message
from config import get_telegram_settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def get_relevant_posts_today() -> List[Dict]:
    """Get only RELEVANT posts from today (ai_relevant = 1)."""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        
        # Get all table names for groups
        cursor.execute("SELECT table_name, group_url FROM Groups ORDER BY group_id")
        groups = cursor.fetchall()
        
        relevant_posts = []
        
        for table_name, group_url in groups:
            posts_table = f"Posts_{table_name}"
            
            # Get ONLY relevant posts from today
            cursor.execute(f"""
                SELECT 
                    internal_post_id,
                    post_content_raw,
                    post_url,
                    scraped_at,
                    '{table_name}' as table_suffix,
                    '{group_url}' as group_url
                FROM {posts_table}
                WHERE DATE(scraped_at) = DATE('now')
                AND ai_relevant = 1
                ORDER BY scraped_at ASC
            """)
            
            group_posts = cursor.fetchall()
            for post in group_posts:
                relevant_posts.append({
                    'internal_post_id': post[0],
                    'content_text': post[1],
                    'post_url': post[2],
                    'scraped_at': post[3],
                    'table_suffix': post[4],
                    'group_url': post[5],
                    'group_name': post[5].split('/')[-1]  # Extract group name from URL
                })
        
        # Sort all posts by scraped_at (oldest first)
        relevant_posts.sort(key=lambda x: x['scraped_at'])
        
        logging.info(f"📋 Found {len(relevant_posts)} RELEVANT posts from today")
        return relevant_posts
        
    except Exception as e:
        logging.error(f"❌ Error getting relevant posts: {e}")
        return []
    finally:
        conn.close()

async def send_relevant_posts():
    """Send only today's relevant posts to Telegram with manual approval."""
    
    # Get relevant posts
    posts = get_relevant_posts_today()
    if not posts:
        logging.info("✅ No relevant posts found from today!")
        return
    
    # Get Telegram settings
    try:
        bot_token, chat_ids = get_telegram_settings()
        if not bot_token or not chat_ids:
            logging.error("❌ Telegram settings not configured")
            return
    except Exception as e:
        logging.error(f"❌ Error getting Telegram settings: {e}")
        return
    
    print(f"\n🎯 Found {len(posts)} relevant posts from today")
    print(f"📱 Will send to {len(chat_ids)} Telegram chats")
    print("=" * 80)
    
    sent_count = 0
    skipped_count = 0
    error_count = 0
    
    for i, post in enumerate(posts, 1):
        try:
            # Clean content
            content = post['content_text']
            clean_content = content.replace('See more', '').replace('Show more', '').replace('… Žr. daugiau', '').replace('Žr. daugiau', '').strip()
            
            # Show post preview
            print(f"\n📋 POST {i}/{len(posts)} - ID: {post['internal_post_id']}")
            print(f"🏷️  GROUP: {post['group_name']}")
            print(f"🕐 SCRAPED: {post['scraped_at']}")
            print(f"📏 LENGTH: {len(clean_content)} characters")
            if post['post_url']:
                print(f"🔗 URL: {post['post_url']}")
            print("-" * 60)
            print("📄 FULL CONTENT:")
            print(f'"{clean_content}"')
            print("-" * 60)
            
            # Ask for approval
            while True:
                choice = input(f"Send this post to Telegram? (y/n/q to quit): ").strip().lower()
                if choice in ['y', 'yes']:
                    break
                elif choice in ['n', 'no']:
                    print("⏭️  Skipping this post...")
                    skipped_count += 1
                    break
                elif choice in ['q', 'quit']:
                    print("\n🛑 Stopping at user request...")
                    print(f"📊 SUMMARY: Sent: {sent_count}, Skipped: {skipped_count}, Remaining: {len(posts) - i + 1}")
                    return
                else:
                    print("❓ Please enter 'y' (yes), 'n' (no), or 'q' (quit)")
            
            # Skip if user said no
            if choice in ['n', 'no']:
                continue
            
            # Format message for Telegram
            message = f"🔥 <b>Relevant Post from {post['group_name']}</b>\n\n"
            message += f"{clean_content}\n\n"
            if post['post_url']:
                message += f"🔗 <a href=\"{post['post_url']}\">View Post</a>\n"
            message += f"📅 {post['scraped_at']}"
            
            # Send to all chat IDs
            print(f"📤 Sending to {len(chat_ids)} chats...")
            for j, chat_id in enumerate(chat_ids, 1):
                try:
                    send_telegram_message(bot_token, chat_id, message, parse_mode="HTML")
                    print(f"  ✅ Sent to chat {j}/{len(chat_ids)}: {chat_id}")
                except Exception as e:
                    print(f"  ❌ Failed to send to chat {chat_id}: {e}")
                    error_count += 1
                
                # Small delay between chats
                await asyncio.sleep(0.5)
            
            sent_count += 1
            print(f"✅ Post {i}/{len(posts)} sent successfully!")
            
            # Small delay before next post
            if i < len(posts):
                await asyncio.sleep(1.0)
            
        except Exception as e:
            error_count += 1
            print(f"❌ Error processing post {post['internal_post_id']}: {e}")
            await asyncio.sleep(1.0)
    
    # Final summary
    print("\n" + "=" * 60)
    print("🎉 MANUAL REVIEW COMPLETE!")
    print(f"✅ Successfully sent: {sent_count}/{len(posts)} posts")
    print(f"⏭️  Skipped: {skipped_count} posts")
    print(f"❌ Errors: {error_count}")
    print("=" * 60)

if __name__ == "__main__":
    print("🎯 Send Today's Relevant Posts")
    print("=" * 50)
    print("This will send ONLY today's AI-relevant posts to Telegram")
    print("Posts will be sent in chronological order (oldest first)")
    print("Delay: 2 seconds between posts")
    print("=" * 50)
    
    confirm = input("Continue? (y/N): ").strip().lower()
    if confirm != 'y':
        print("❌ Cancelled")
        sys.exit(0)
    
    # Run the sending
    asyncio.run(send_relevant_posts()) 