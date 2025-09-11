#!/usr/bin/env python3
"""
Resend All Posts Script for Scrapius Bot
Sends all posts from the database to Telegram, ordered from oldest to newest.
"""

import sqlite3
import logging
import time
import sys
from typing import List, Dict

from config import get_telegram_settings
from database.crud import get_db_connection
from database.simple_per_group import list_all_groups
from notifier.telegram_notifier import send_telegram_message, format_post_message

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_all_posts_from_all_groups(conn) -> List[Dict]:
    """
    Get all posts from all group tables, ordered by scraped_at (oldest first).
    
    Returns:
        List of post dictionaries with group information
    """
    all_posts = []
    
    try:
        # Get all groups
        groups = list_all_groups(conn)
        logging.info(f"📊 Found {len(groups)} groups to process")
        
        for group in groups:
            group_id = group['group_id']
            group_name = group['group_name']
            group_url = group['group_url']
            table_name = group['table_name']
            
            logging.info(f"📋 Processing group: {group_name}")
            
            # Get all posts from this group's table
            cursor = conn.cursor()
            posts_table = f"Posts_{table_name}"
            
            try:
                cursor.execute(f"""
                    SELECT 
                        internal_post_id,
                        facebook_post_id,
                        post_url,
                        post_content_raw,
                        scraped_at,
                        content_hash
                    FROM {posts_table} 
                    ORDER BY internal_post_id ASC
                """)
                
                posts = cursor.fetchall()
                logging.info(f"  📝 Found {len(posts)} posts in {posts_table}")
                
                # Convert to dictionaries and add group info
                for post in posts:
                    post_dict = {
                        'internal_post_id': post[0],
                        'facebook_post_id': post[1],
                        'post_url': post[2],
                        'post_content_raw': post[3],
                        'scraped_at': post[4],
                        'content_hash': post[5],
                        'group_id': group_id,
                        'group_name': group_name,
                        'group_url': group_url,
                        'table_name': table_name
                    }
                    all_posts.append(post_dict)
                    
            except sqlite3.Error as e:
                logging.error(f"❌ Error reading from {posts_table}: {e}")
                continue
                
    except Exception as e:
        logging.error(f"❌ Error getting posts: {e}")
        return []
    
    # Sort all posts by scraped_at (oldest first)
    all_posts.sort(key=lambda x: x['scraped_at'] or '0')
    
    logging.info(f"📊 Total posts collected: {len(all_posts)}")
    return all_posts

def resend_post_to_telegram(post: Dict, bot_token: str, chat_ids: List[str], delay: float = 1.0) -> bool:
    """
    Send a single post to Telegram.
    
    Args:
        post: Post dictionary
        bot_token: Telegram bot token
        chat_ids: List of chat IDs to send to
        delay: Delay between messages to avoid rate limiting
        
    Returns:
        True if sent successfully, False otherwise
    """
    try:
        # Format the message
        title = "📩 Resent Post"
        content = post.get('post_content_raw', '')
        
        # Clean and truncate content
        clean_content = content.replace('See more', '').replace('Show more', '').replace('… Žr. daugiau', '').replace('Žr. daugiau', '').strip()
        short_text = clean_content[:300] + '...' if len(clean_content) > 300 else clean_content
        
        # Use post URL or group URL as fallback
        post_url = post.get('post_url') or post.get('group_url', '#')
        group_name = post.get('group_name', 'Unknown Group')
        
        message = format_post_message(title, short_text, post_url, None, group_name)
        
        # Add timestamp info
        scraped_at = post.get('scraped_at', 'Unknown')
        message += f"\n\n🕐 <i>Originally scraped: {scraped_at}</i>"
        
        # Send to group chats only (negative IDs)
        group_chats = [chat_id for chat_id in chat_ids if chat_id.startswith('-')]
        
        if not group_chats:
            logging.warning("⚠️ No group chats configured for notifications")
            return False
        
        success_count = 0
        for chat_id in group_chats:
            try:
                success = send_telegram_message(bot_token, chat_id, message, parse_mode="HTML")
                if success:
                    success_count += 1
                    logging.info(f"✅ Sent post {post['internal_post_id']} to chat {chat_id}")
                else:
                    logging.warning(f"⚠️ Failed to send post {post['internal_post_id']} to chat {chat_id}")
                
                # Rate limiting delay
                time.sleep(delay)
                
            except Exception as e:
                logging.error(f"❌ Error sending to chat {chat_id}: {e}")
                continue
        
        return success_count > 0
        
    except Exception as e:
        logging.error(f"❌ Error formatting/sending post {post.get('internal_post_id')}: {e}")
        return False

def main():
    """Main function to resend all posts."""
    print("🚀 Scrapius Post Resender")
    print("=" * 50)
    
    # Get database connection
    conn = get_db_connection()
    if not conn:
        logging.error("❌ Failed to connect to database")
        sys.exit(1)
    
    # Get Telegram settings
    bot_token, chat_ids = get_telegram_settings()
    if not bot_token or not chat_ids:
        logging.error("❌ Telegram settings not configured")
        sys.exit(1)
    
    logging.info(f"📱 Bot token configured, sending to {len(chat_ids)} chats")
    
    # Get all posts
    logging.info("📊 Collecting all posts from database...")
    all_posts = get_all_posts_from_all_groups(conn)
    
    if not all_posts:
        logging.info("📭 No posts found in database")
        conn.close()
        return
    
    # Confirm with user
    print(f"\n📊 Found {len(all_posts)} posts to resend")
    print("⚠️  This will send ALL posts from oldest to newest")
    print("⚠️  This may take a while and could trigger rate limits")
    
    confirm = input("\n❓ Are you sure you want to continue? (yes/no): ").lower().strip()
    if confirm not in ['yes', 'y']:
        print("❌ Cancelled by user")
        conn.close()
        return
    
    # Ask for delay between messages
    try:
        delay = float(input("⏱️  Delay between messages in seconds (default 2.0): ") or "2.0")
    except ValueError:
        delay = 2.0
    
    print(f"\n🚀 Starting to resend {len(all_posts)} posts with {delay}s delay...")
    print("=" * 50)
    
    # Send posts
    sent_count = 0
    failed_count = 0
    
    for i, post in enumerate(all_posts, 1):
        try:
            print(f"📤 [{i}/{len(all_posts)}] Sending post from {post['group_name'][:30]}...")
            
            success = resend_post_to_telegram(post, bot_token, chat_ids, delay)
            
            if success:
                sent_count += 1
            else:
                failed_count += 1
                
        except KeyboardInterrupt:
            print(f"\n⏹️  Interrupted by user after {sent_count} posts")
            break
        except Exception as e:
            logging.error(f"❌ Unexpected error processing post {i}: {e}")
            failed_count += 1
            continue
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 RESEND SUMMARY")
    print("=" * 50)
    print(f"✅ Successfully sent: {sent_count}")
    print(f"❌ Failed: {failed_count}")
    print(f"📊 Total processed: {sent_count + failed_count}")
    print("=" * 50)
    
    conn.close()
    logging.info("🏁 Resend operation completed")

if __name__ == "__main__":
    main() 