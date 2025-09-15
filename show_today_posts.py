#!/usr/bin/env python3
"""
Show all posts from today with full content and group names.
"""

import sqlite3
import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.crud import get_db_connection

def show_all_posts_today():
    """Show all posts from today with full content and group names."""
    conn = get_db_connection()
    if not conn:
        print("❌ Cannot connect to database")
        return
    
    try:
        cursor = conn.cursor()
        
        # Get all groups with their URLs for reference
        cursor.execute("SELECT group_id, group_url, table_name FROM Groups ORDER BY group_id")
        groups = cursor.fetchall()
        
        all_posts = []
        
        print("🔍 Collecting posts from all groups...")
        
        for group_id, group_url, table_name in groups:
            posts_table = f"Posts_{table_name}"
            
            # Get all posts from today for this group
            cursor.execute(f"""
                SELECT 
                    internal_post_id,
                    post_content_raw,
                    post_url,
                    scraped_at,
                    ai_relevant,
                    ai_processed_at
                FROM {posts_table}
                WHERE DATE(scraped_at) = DATE('now')
                ORDER BY scraped_at ASC
            """)
            
            group_posts = cursor.fetchall()
            for post in group_posts:
                all_posts.append({
                    'group_id': group_id,
                    'group_url': group_url,
                    'group_name': group_url.split('/')[-1],  # Extract group name from URL
                    'internal_post_id': post[0],
                    'content_text': post[1],
                    'post_url': post[2],
                    'scraped_at': post[3],
                    'ai_relevant': post[4],
                    'ai_processed_at': post[5]
                })
        
        # Sort all posts by scraped_at (oldest first)
        all_posts.sort(key=lambda x: x['scraped_at'])
        
        print(f"\n📊 Found {len(all_posts)} posts from today")
        print("=" * 80)
        
        # Group posts by group for summary
        group_counts = {}
        for post in all_posts:
            group_name = post['group_name']
            if group_name not in group_counts:
                group_counts[group_name] = 0
            group_counts[group_name] += 1
        
        print("📋 Posts per group:")
        for group_name, count in sorted(group_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"   • {group_name}: {count} posts")
        
        print("\n" + "=" * 80)
        print("📝 FULL CONTENT OF ALL POSTS:")
        print("=" * 80)
        
        for i, post in enumerate(all_posts, 1):
            ai_status = "✅ Relevant" if post['ai_relevant'] == 1 else "⚪ Not relevant" if post['ai_relevant'] == 0 else "❓ Unprocessed"
            
            print(f"\n[{i}/{len(all_posts)}] POST ID: {post['internal_post_id']}")
            print(f"🏷️  GROUP: {post['group_name']}")
            print(f"🕐 SCRAPED: {post['scraped_at']}")
            print(f"🤖 AI STATUS: {ai_status}")
            print(f"📏 LENGTH: {len(post['content_text'])} characters")
            print(f"🔗 URL: {post['post_url'] or 'N/A'}")
            print("-" * 40)
            print("📄 FULL CONTENT:")
            print(f'"{post["content_text"]}"')
            print("=" * 80)
            
            # Add a pause every 10 posts for readability
            if i % 10 == 0 and i < len(all_posts):
                input(f"\n⏸️  Shown {i}/{len(all_posts)} posts. Press Enter to continue...")
        
        print(f"\n🎉 Displayed all {len(all_posts)} posts from today!")
        
        # Final summary
        relevant_count = sum(1 for p in all_posts if p['ai_relevant'] == 1)
        not_relevant_count = sum(1 for p in all_posts if p['ai_relevant'] == 0)
        unprocessed_count = sum(1 for p in all_posts if p['ai_relevant'] is None)
        
        print("\n📊 FINAL SUMMARY:")
        print(f"   ✅ Relevant: {relevant_count}")
        print(f"   ⚪ Not relevant: {not_relevant_count}")
        print(f"   ❓ Unprocessed: {unprocessed_count}")
        print(f"   📝 Total: {len(all_posts)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    print("📋 Today's Posts Viewer")
    print("=" * 50)
    print("This will show ALL posts from today with full content")
    print("Posts will be grouped and displayed chronologically")
    print("=" * 50)
    
    confirm = input("Continue? (y/N): ").strip().lower()
    if confirm != 'y':
        print("❌ Cancelled")
        sys.exit(0)
    
    show_all_posts_today() 