#!/usr/bin/env python3
"""
Fix Database Timezone from UTC to EEST (GMT+3)
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

def convert_table_timezone(conn, table_name):
    """Convert UTC timestamps to EEST in a table."""
    cursor = conn.cursor()
    
    # Get all records with timestamps
    cursor.execute(f"SELECT internal_post_id, scraped_at, ai_processed_at FROM {table_name}")
    rows = cursor.fetchall()
    
    if not rows:
        logging.info(f"📝 {table_name}: No records to convert")
        return 0
    
    converted = 0
    for row in rows:
        post_id, scraped_at, ai_processed_at = row
        
        # Convert scraped_at from UTC to EEST
        if scraped_at:
            try:
                dt_utc = datetime.fromisoformat(scraped_at.replace('Z', ''))
                dt_eest = dt_utc + timedelta(hours=3)
                new_scraped_at = dt_eest.strftime('%Y-%m-%d %H:%M:%S')
            except:
                new_scraped_at = scraped_at  # Keep original if conversion fails
        else:
            new_scraped_at = scraped_at
        
        # Convert ai_processed_at from UTC to EEST
        if ai_processed_at:
            try:
                dt_utc = datetime.fromisoformat(ai_processed_at.replace('Z', ''))
                dt_eest = dt_utc + timedelta(hours=3)
                new_ai_processed_at = dt_eest.strftime('%Y-%m-%d %H:%M:%S')
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
        
        converted += 1
    
    logging.info(f"✅ {table_name}: Converted {converted} records from UTC to EEST")
    return converted

def main():
    """Convert all timestamps from UTC to EEST."""
    logging.info("🕐 Starting timezone conversion: UTC → EEST (GMT+3)")
    
    try:
        conn = get_db_connection()
        tables = get_all_posts_tables(conn)
        
        if not tables:
            logging.warning("⚠️ No Posts tables found")
            return
        
        logging.info(f"📋 Found {len(tables)} tables to convert")
        
        total_converted = 0
        for table in tables:
            converted = convert_table_timezone(conn, table)
            total_converted += converted
        
        # Commit all changes
        conn.commit()
        conn.close()
        
        logging.info(f"🎉 Timezone conversion complete! Converted {total_converted} records total")
        logging.info("📝 All timestamps are now in EEST (GMT+3)")
        
    except Exception as e:
        logging.error(f"❌ Conversion failed: {e}")
        raise

if __name__ == "__main__":
    main() 