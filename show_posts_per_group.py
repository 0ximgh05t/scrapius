#!/usr/bin/env python3
"""
Show Posts Per Group Statistics
"""

import sqlite3
from database.crud import get_db_connection
from database.simple_per_group import list_all_groups

def show_posts_per_group():
    """Show post counts for each group."""
    try:
        conn = get_db_connection()
        
        # Get all groups
        groups = list_all_groups(conn)
        
        if not groups:
            print("📭 No groups found in database")
            return
        
        print(f"📊 Posts per Group ({len(groups)} groups total):")
        print("=" * 60)
        
        total_posts = 0
        
        for group in groups:
            group_id = group['group_id']
            group_url = group['group_url']
            table_suffix = group['table_name']
            posts_table = f"Posts_{table_suffix}"
            
            # Get post count (already included in the group dict)
            cursor = conn.cursor()
            post_count = group.get('post_count', 0)
            
            # Get AI processed count (if column exists)
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {posts_table} WHERE ai_relevant IS NOT NULL")
                ai_processed = cursor.fetchone()[0]
                
                cursor.execute(f"SELECT COUNT(*) FROM {posts_table} WHERE ai_relevant = 1")
                ai_relevant = cursor.fetchone()[0]
                
                ai_info = f" | AI: {ai_processed} processed, {ai_relevant} relevant"
            except:
                ai_info = " | AI: columns not found"
            
            # Get latest post date
            try:
                cursor.execute(f"SELECT MAX(scraped_at) FROM {posts_table}")
                latest = cursor.fetchone()[0]
                latest_info = f" | Latest: {latest}" if latest else " | Latest: None"
            except:
                latest_info = ""
            
            # Extract group name from URL
            group_name = group_url.split('/')[-1] if group_url else f"Group_{group_id}"
            
            print(f"🔸 {group_name}")
            print(f"   📝 {post_count} posts{ai_info}{latest_info}")
            print(f"   🔗 {group_url}")
            print()
            
            total_posts += post_count
        
        print("=" * 60)
        print(f"📊 TOTAL: {total_posts} posts across {len(groups)} groups")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    show_posts_per_group() 