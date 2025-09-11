#!/usr/bin/env python3
"""
Database Schema Migration Script
Adds missing ai_relevant and ai_processed_at columns to existing tables.
"""

import sqlite3
import logging
from database.crud import get_db_connection

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_all_posts_tables(conn):
    """Get all Posts_* table names from the database."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Posts_%'")
    return [row[0] for row in cursor.fetchall()]

def add_missing_columns(conn, table_name):
    """Add missing columns to a specific table."""
    cursor = conn.cursor()
    
    # Check if ai_relevant column exists
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    
    changes_made = False
    
    # Add ai_relevant column if missing
    if 'ai_relevant' not in columns:
        try:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN ai_relevant INTEGER DEFAULT NULL")
            logging.info(f"✅ Added ai_relevant column to {table_name}")
            changes_made = True
        except sqlite3.OperationalError as e:
            logging.error(f"❌ Failed to add ai_relevant to {table_name}: {e}")
    
    # Add ai_processed_at column if missing
    if 'ai_processed_at' not in columns:
        try:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN ai_processed_at TIMESTAMP DEFAULT NULL")
            logging.info(f"✅ Added ai_processed_at column to {table_name}")
            changes_made = True
        except sqlite3.OperationalError as e:
            logging.error(f"❌ Failed to add ai_processed_at to {table_name}: {e}")
    
    if not changes_made:
        logging.info(f"📝 {table_name} already has all required columns")
    
    return changes_made

def main():
    """Main migration function."""
    logging.info("🔧 Starting database schema migration...")
    
    try:
        # Get database connection
        conn = get_db_connection()
        
        # Get all Posts tables
        tables = get_all_posts_tables(conn)
        logging.info(f"📋 Found {len(tables)} Posts tables to check")
        
        if not tables:
            logging.warning("⚠️ No Posts tables found in database")
            return
        
        # Process each table
        total_changes = 0
        for table in tables:
            logging.info(f"🔍 Checking table: {table}")
            if add_missing_columns(conn, table):
                total_changes += 1
        
        # Commit changes
        if total_changes > 0:
            conn.commit()
            logging.info(f"✅ Migration complete! Updated {total_changes} tables")
        else:
            logging.info("📝 No changes needed - all tables are up to date")
        
        # Verify the changes
        logging.info("🔍 Verifying migration...")
        for table in tables:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [row[1] for row in cursor.fetchall()]
            
            has_ai_relevant = 'ai_relevant' in columns
            has_ai_processed_at = 'ai_processed_at' in columns
            
            status = "✅" if (has_ai_relevant and has_ai_processed_at) else "❌"
            logging.info(f"{status} {table}: ai_relevant={has_ai_relevant}, ai_processed_at={has_ai_processed_at}")
        
        conn.close()
        logging.info("🎉 Database migration completed successfully!")
        
    except Exception as e:
        logging.error(f"❌ Migration failed: {e}")
        raise

if __name__ == "__main__":
    main() 