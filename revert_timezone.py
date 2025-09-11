#!/usr/bin/env python3
"""
Revert Database Timezone from EEST back to UTC
(Fix the double conversion mistake)
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from database.crud import get_db_connection

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_all_posts_tables(conn):
    """Get all Posts_* table names."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Posts_%'")
    return [row[0] for row in cursor.fetchall()]

def revert_table_timezone(conn, table_name):
    """Convert EEST timestamps back to UTC."""
    cursor = conn.cursor()
    
    # Get all records with timestamps
    cursor.execute(f"SELECT internal_post_id, scraped_at, ai_processed_at FROM {table_name}")
    rows = cursor.fetchall()
    
    if not rows:
        logging.info(f"📝 {table_name}: No records to revert")
        return 0
    
    reverted = 0
    for row in rows:
        post_id, scraped_at, ai_processed_at = row
        
        # Convert scraped_at from EEST back to UTC
        if scraped_at:
            try:
                dt_eest = datetime.fromisoformat(scraped_at.replace('Z', ''))
                dt_utc = dt_eest - timedelta(hours=3)  # Subtract 3 hours
                new_scraped_at = dt_utc.strftime('%Y-%m-%d %H:%M:%S')
            except:
                new_scraped_at = scraped_at  # Keep original if conversion fails
        else:
            new_scraped_at = scraped_at
        
        # Convert ai_processed_at from EEST back to UTC
        if ai_processed_at:
            try:
                dt_eest = datetime.fromisoformat(ai_processed_at.replace('Z', ''))
                dt_utc = dt_eest - timedelta(hours=3)  # Subtract 3 hours
                new_ai_processed_at = dt_utc.strftime('%Y-%m-%d %H:%M:%S')
            except:
                new_ai_processed_at = ai_processed_at  # Keep original if conversion fails
        else:
            new_ai_processed_at = ai_processed_at
        
        # Update the record
        cursor.execute(f"""
            UPDATE {table_name} 
            SET scraped_at = ?, ai_processed_at = ?
            WHERE internal_post_id = ?
        """, (new_scraped_at, new_ai_processed_at, post_id))
        
        reverted += 1
    
    logging.info(f"✅ {table_name}: Reverted {reverted} records from EEST to UTC")
    return reverted

def main():
    """Revert all timestamps from EEST back to UTC."""
    logging.info("🔄 Reverting timezone conversion: EEST → UTC (fixing double conversion)")
    
    try:
        conn = get_db_connection()
        tables = get_all_posts_tables(conn)
        
        if not tables:
            logging.warning("⚠️ No Posts tables found")
            return
        
        logging.info(f"📋 Found {len(tables)} tables to revert")
        
        total_reverted = 0
        for table in tables:
            reverted = revert_table_timezone(conn, table)
            total_reverted += reverted
        
        # Commit all changes
        conn.commit()
        conn.close()
        
        logging.info(f"🎉 Timezone reversion complete! Reverted {total_reverted} records total")
        logging.info("📝 All timestamps are now back to UTC (display will convert to EEST)")
        
    except Exception as e:
        logging.error(f"❌ Reversion failed: {e}")
        raise

if __name__ == "__main__":
    main() 