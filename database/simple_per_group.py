import sqlite3
import logging
import re
from typing import Dict, Optional, Tuple, List
# Selenium imports moved to function level to avoid import issues

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def _scrape_group_name_from_page(driver) -> Optional[str]:
    """
    Scrape the actual Facebook group name from the current page.
    
    Args:
        driver: WebDriver instance (should already be on the group page)
        
    Returns:
        Group name if found, None otherwise
    """
    # Import Selenium only when needed
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    try:
        logging.info(f"🔍 Starting group name extraction. Current URL: {driver.current_url}")
        
        # Enhanced selectors for Facebook group names (based on actual FB structure)
        selectors = [
            'h1[dir="auto"] span a',  # Most specific: h1 > span > a (contains actual name)
            'h1[dir="auto"] a',      # Fallback: direct h1 > a
            'h1 a[href*="/groups/"]', # More specific: h1 > a with groups href
            'h1[dir="auto"]',        # Fallback: entire h1
            'h1 a',                  # Generic: any h1 > a
            'h1'                     # Last resort: any h1
        ]
        
        for selector in selectors:
            try:
                logging.debug(f"🔍 Trying selector: {selector}")
                element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                text = element.text.strip()
                logging.debug(f"📝 Found text with selector '{selector}': '{text}'")
                
                # Filter out common Facebook UI elements and improve validation
                if (text and 
                    len(text) > 2 and 
                    len(text) < 150 and
                    'Facebook' not in text and
                    'See all' not in text and
                    'More' not in text and
                    'home' not in text.lower() and
                    'Join' not in text and
                    'Invite' not in text and
                    'Search' not in text and
                    not text.isdigit() and
                    'members' not in text.lower()):
                    
                    logging.info(f"✅ Scraped group name: '{text}' using selector: {selector}")
                    return text
                else:
                    logging.debug(f"❌ Text '{text}' filtered out (doesn't meet criteria)")
                    
            except (TimeoutException, NoSuchElementException) as e:
                logging.debug(f"❌ Selector '{selector}' failed: {e}")
                continue
                
        logging.warning("❌ Could not scrape group name from page")
        return None
        
    except Exception as e:
        logging.error(f"Error scraping group name: {e}")
        return None

def sanitize_table_name(group_url: str) -> str:
    """
    Generate a safe table name from group URL.
    Example: 'https://facebook.com/groups/501702489979518' -> 'Group_501702489979518'
    """
    # Extract numeric ID from URL
    match = re.search(r'/groups/(\d+)', group_url)
    if match:
        group_numeric_id = match.group(1)
        return f"Group_{group_numeric_id}"
    else:
        # Fallback: use hash of URL
        import hashlib
        url_hash = hashlib.md5(group_url.encode()).hexdigest()[:10]
        return f"Group_{url_hash}"

def create_group_posts_table(db_conn: sqlite3.Connection, table_suffix: str) -> bool:
    """
    Create Posts table for a specific group.
    
    Args:
        db_conn: Database connection
        table_suffix: Safe table name suffix (e.g., 'Group_501702489979518')
        
    Returns:
        True if successful, False otherwise
    """
    try:
        cursor = db_conn.cursor()
        posts_table = f"Posts_{table_suffix}"
        
        # Create Posts table for this group (NO COMMENTS!)
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {posts_table} (
                internal_post_id INTEGER PRIMARY KEY AUTOINCREMENT,
                facebook_post_id TEXT,
                post_url TEXT,
                post_content_raw TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                content_hash TEXT UNIQUE
            )
        ''')
        
        # Add content_hash column if it doesn't exist (for existing tables)
        try:
            cursor.execute(f"ALTER TABLE {posts_table} ADD COLUMN content_hash TEXT")
            logging.info(f"✅ Added content_hash column to {posts_table}")
        except sqlite3.OperationalError:
            # Column already exists, which is fine
            pass
        
        db_conn.commit()
        logging.info(f"✅ Created table {posts_table}")
        return True
        
    except sqlite3.Error as e:
        logging.error(f"❌ Error creating group table: {e}")
        db_conn.rollback()
        return False

def get_or_create_group(db_conn: sqlite3.Connection, group_url: str, group_name: str = None, driver=None) -> Tuple[int, str]:
    """
    Get existing group or create new one with dedicated posts table.
    
    Args:
        db_conn: Database connection
        group_url: Facebook group URL
        group_name: Optional group name (if None and driver provided, will scrape from page)
        driver: Optional WebDriver to scrape group name from Facebook
        
    Returns:
        Tuple of (group_id, table_suffix)
    """
    try:
        cursor = db_conn.cursor()
        
        # Check if group exists
        cursor.execute("SELECT group_id, table_name FROM Groups WHERE group_url = ?", (group_url,))
        result = cursor.fetchone()
        
        if result:
            group_id, table_suffix = result
            logging.info(f"📋 Found existing group {group_id} -> {table_suffix}")
            return group_id, table_suffix
        
        # Create new group
        table_suffix = sanitize_table_name(group_url)
        
        if not group_name:
            # Try to scrape group name from Facebook if driver is provided
            if driver:
                logging.info(f"🔍 Attempting to scrape group name from Facebook page...")
                group_name = _scrape_group_name_from_page(driver)
                if group_name:
                    logging.info(f"✅ Successfully scraped group name: '{group_name}'")
                else:
                    logging.warning(f"❌ Failed to scrape group name from Facebook page")
            else:
                logging.warning(f"❌ No driver provided for group name scraping")
            
            # Fallback to URL-based name
            if not group_name:
                logging.info(f"🔄 Using fallback group name for {group_url}")
                group_name = f"Group from {group_url}"
        
        logging.info(f"🔍 Attempting to create group: name='{group_name}', url='{group_url}', table='{table_suffix}'")
        
        cursor.execute(
            "INSERT INTO Groups (group_name, group_url, table_name) VALUES (?, ?, ?)",
            (group_name, group_url, table_suffix)
        )
        
        group_id = cursor.lastrowid
        logging.info(f"✅ Group created with ID: {group_id}")
        
        # Create dedicated posts table for this group
        if create_group_posts_table(db_conn, table_suffix):
            db_conn.commit()
            logging.info(f"🎯 Created new group {group_id} -> Posts_{table_suffix}")
            return group_id, table_suffix
        else:
            raise Exception("Failed to create group posts table")
            
    except sqlite3.IntegrityError as e:
        # Handle unique constraint violations - group might already exist
        logging.warning(f"⚠️ Integrity error (likely duplicate): {e}")
        db_conn.rollback()
        
        # Try to find the existing group again
        cursor = db_conn.cursor()
        cursor.execute("SELECT group_id, table_name FROM Groups WHERE group_url = ? OR table_name = ?", (group_url, table_suffix))
        result = cursor.fetchone()
        if result:
            group_id, existing_table_suffix = result
            logging.info(f"📋 Found existing group after integrity error: {group_id} -> {existing_table_suffix}")
            return group_id, existing_table_suffix
        else:
            logging.error(f"❌ Could not find group after integrity error: {e}")
            raise
    except sqlite3.Error as e:
        logging.error(f"❌ Error in get_or_create_group: {e}")
        db_conn.rollback()
        raise

def add_post_to_group(db_conn: sqlite3.Connection, table_suffix: str, post_data: Dict) -> Optional[Tuple[int, bool]]:
    """
    Add a post to the group-specific table.
    
    Args:
        db_conn: Database connection
        table_suffix: Group table suffix (e.g., 'Group_501702489979518')
        post_data: Post data dictionary
        
    Returns:
        Tuple of (internal_post_id, is_new) or None if failed
    """
    try:
        cursor = db_conn.cursor()
        posts_table = f"Posts_{table_suffix}"
        
        # Check if post already exists
        post_url = post_data.get('post_url')
        facebook_post_id = post_data.get('facebook_post_id')
        content_hash = post_data.get('content_hash')
        
        # Check ONLY by content_hash - content is what matters, not URL or ID
        cursor.execute(f"""
            SELECT internal_post_id FROM {posts_table} 
            WHERE content_hash = ?
        """, (content_hash,))
        
        existing = cursor.fetchone()
        if existing:
            # Check if this is the same content (by hash) or updated content
            cursor.execute(f"SELECT content_hash FROM {posts_table} WHERE internal_post_id = ?", (existing[0],))
            existing_hash = cursor.fetchone()[0]
            
            if existing_hash == content_hash:
                logging.info(f"📝 Post already exists with same content in {posts_table} with ID {existing[0]}")
                return existing[0], False
            else:
                # Same post URL/ID but different content - update it
                logging.info(f"🔄 Updating existing post {existing[0]} with new content (hash changed: {existing_hash[:12]}... → {content_hash[:12]}...)")
                cursor.execute(f"""
                    UPDATE {posts_table} 
                    SET post_content_raw = ?, content_hash = ?, scraped_at = CURRENT_TIMESTAMP
                    WHERE internal_post_id = ?
                """, (post_data.get('content_text'), content_hash, existing[0]))
                db_conn.commit()
                return existing[0], True  # Return True to indicate it was updated (treat as new)
        
        # Insert new post
        cursor.execute(f"""
            INSERT OR IGNORE INTO {posts_table} (
                facebook_post_id, post_url, post_content_raw, content_hash
            ) VALUES (?, ?, ?, ?)
        """, (
            post_data.get('facebook_post_id'),
            post_data.get('post_url'),
            post_data.get('content_text'),
            post_data.get('content_hash')
        ))
        
        if cursor.rowcount > 0:
            post_id = cursor.lastrowid
            db_conn.commit()
            logging.info(f"✅ Added new post to {posts_table} with ID {post_id}")
            return post_id, True
        else:
            logging.info(f"📝 Post already exists in {posts_table} (INSERT OR IGNORE)")
            return None, False
            
    except sqlite3.Error as e:
        logging.error(f"❌ Error adding post to {table_suffix}: {e}")
        db_conn.rollback()
        return None

def get_most_recent_facebook_post_id(db_conn: sqlite3.Connection, table_suffix: str) -> str | None:
    """
    Get the most recent Facebook post ID from database for super simple duplicate checking.
    
    Args:
        db_conn: Database connection
        table_suffix: Group table suffix (e.g., 'Group_123456')
        
    Returns:
        Most recent facebook_post_id or None if no posts exist
    """
    try:
        cursor = db_conn.cursor()
        posts_table = f"Posts_{table_suffix}"
        
        cursor.execute(f"""
            SELECT facebook_post_id FROM {posts_table} 
            WHERE facebook_post_id IS NOT NULL AND facebook_post_id != ''
            AND facebook_post_id NOT LIKE 'generated_%'
            ORDER BY internal_post_id DESC
            LIMIT 1
        """)
        
        result = cursor.fetchone()
        return result[0] if result else None
        
    except sqlite3.Error as e:
        logging.error(f"❌ Error getting most recent Facebook post ID from {table_suffix}: {e}")
        return None

def get_most_recent_post_content_hash(db_conn: sqlite3.Connection, table_suffix: str) -> str | None:
    """
    Get the most recent post content_hash from a specific group table for incremental scraping.
    
    Args:
        db_conn: Database connection
        table_suffix: Group table suffix (e.g., 'Group_123456')
        
    Returns:
        Most recent content_hash or None if no posts exist
    """
    try:
        cursor = db_conn.cursor()
        posts_table = f"Posts_{table_suffix}"
        
        cursor.execute(f"""
            SELECT content_hash FROM {posts_table} 
            WHERE content_hash IS NOT NULL AND content_hash != ''
            ORDER BY internal_post_id DESC
            LIMIT 1
        """)
        
        result = cursor.fetchone()
        return result[0] if result else None
        
    except sqlite3.Error as e:
        logging.error(f"❌ Error getting most recent content hash from {table_suffix}: {e}")
        return None

def get_most_recent_post_url(db_conn: sqlite3.Connection, table_suffix: str) -> str | None:
    """
    DEPRECATED: Get the most recent post URL (kept for backwards compatibility).
    Use get_most_recent_post_content_hash() instead for better incremental scraping.
    """
    try:
        cursor = db_conn.cursor()
        posts_table = f"Posts_{table_suffix}"
        
        cursor.execute(f"""
            SELECT post_url FROM {posts_table} 
            WHERE post_url IS NOT NULL AND post_url != ''
            ORDER BY internal_post_id DESC
            LIMIT 1
        """)
        
        result = cursor.fetchone()
        return result[0] if result else None
        
    except sqlite3.Error as e:
        logging.error(f"❌ Error getting most recent URL from {table_suffix}: {e}")
        return None

def get_group_posts(db_conn: sqlite3.Connection, table_suffix: str, limit: int = 20) -> List[Dict]:
    """
    Get posts from a specific group table.
    
    Args:
        db_conn: Database connection
        table_suffix: Group table suffix
        limit: Maximum number of posts to return
        
    Returns:
        List of post dictionaries
    """
    try:
        cursor = db_conn.cursor()
        posts_table = f"Posts_{table_suffix}"
        
        cursor.execute(f"""
            SELECT * FROM {posts_table} 
            ORDER BY internal_post_id DESC 
            LIMIT ?
        """, (limit,))
        
        posts = []
        for row in cursor.fetchall():
            post_dict = dict(row)
            posts.append(post_dict)
        
        return posts
        
    except sqlite3.Error as e:
        logging.error(f"❌ Error getting posts from {table_suffix}: {e}")
        return []

def list_all_groups(db_conn: sqlite3.Connection) -> List[Dict]:
    """
    List all groups with their post counts.
    
    Returns:
        List of group dictionaries with post counts
    """
    try:
        cursor = db_conn.cursor()
        cursor.execute("SELECT * FROM Groups ORDER BY group_id")
        
        groups = []
        for row in cursor.fetchall():
            group_dict = dict(row)
            
            # Get post count for this group
            table_suffix = group_dict['table_name']
            posts_table = f"Posts_{table_suffix}"
            
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {posts_table}")
                post_count = cursor.fetchone()[0]
                group_dict['post_count'] = post_count
            except sqlite3.Error:
                group_dict['post_count'] = 0
            
            groups.append(group_dict)
        
        return groups
        
    except sqlite3.Error as e:
        logging.error(f"❌ Error listing groups: {e}")
        return []

def drop_group_table(db_conn: sqlite3.Connection, group_id: int) -> bool:
    """
    Drop posts table for a specific group and remove from Groups table.
    
    Args:
        db_conn: Database connection
        group_id: Group ID to remove
        
    Returns:
        True if successful
    """
    try:
        cursor = db_conn.cursor()
        
        # Get table suffix
        cursor.execute("SELECT table_name FROM Groups WHERE group_id = ?", (group_id,))
        result = cursor.fetchone()
        
        if not result:
            logging.warning(f"⚠️ Group {group_id} not found")
            return False
        
        table_suffix = result[0]
        posts_table = f"Posts_{table_suffix}"
        
        # Drop posts table
        cursor.execute(f"DROP TABLE IF EXISTS {posts_table}")
        
        # Remove from Groups table
        cursor.execute("DELETE FROM Groups WHERE group_id = ?", (group_id,))
        
        db_conn.commit()
        logging.info(f"🗑️ Dropped {posts_table} and removed group {group_id}")
        return True
        
    except sqlite3.Error as e:
        logging.error(f"❌ Error dropping group {group_id}: {e}")
        db_conn.rollback()
        return False

def content_hash_exists(db_conn: sqlite3.Connection, table_suffix: str, content_hash: str) -> bool:
    """
    Check if a content hash already exists in the database.
    
    Args:
        db_conn: Database connection
        table_suffix: Group table suffix
        content_hash: Content hash to check
        
    Returns:
        True if hash exists, False otherwise
    """
    try:
        cursor = db_conn.cursor()
        posts_table = f"Posts_{table_suffix}"
        
        cursor.execute(f"""
            SELECT 1 FROM {posts_table} 
            WHERE content_hash = ? 
            LIMIT 1
        """, (content_hash,))
        
        return cursor.fetchone() is not None
        
    except sqlite3.Error:
        return False

# Helper function for Telegram bot
def get_latest_post_url(db_conn: sqlite3.Connection, table_suffix: str) -> Optional[str]:
    """
    Get the most recent post URL for incremental scraping.
    
    Args:
        db_conn: Database connection
        table_suffix: Group table suffix
        
    Returns:
        Most recent post URL or None
    """
    try:
        cursor = db_conn.cursor()
        posts_table = f"Posts_{table_suffix}"
        
        # Only use real Facebook post URLs for incremental scraping, not group URLs or generated ones
        cursor.execute(f"""
            SELECT post_url FROM {posts_table} 
            WHERE post_url NOT LIKE '%no_url_generated_%'
            AND post_url LIKE '%facebook.com%'
            AND post_url LIKE '%/posts/%'
            ORDER BY internal_post_id DESC 
            LIMIT 1
        """)
        
        result = cursor.fetchone()
        return result[0] if result else None
        
    except sqlite3.Error as e:
        logging.error(f"❌ Error getting latest post from {table_suffix}: {e}")
        return None 