import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def init_db(db_name='insights.db'):
    """
    Initializes the SQLite database and creates required tables if they don't exist.
    Now supports multiple Facebook groups with Groups table.

    Args:
        db_name: The name of the SQLite database file.
    """
    conn = None
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Groups (
                group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_name TEXT UNIQUE NOT NULL,
                group_url TEXT UNIQUE NOT NULL,
                table_name TEXT UNIQUE NOT NULL,
                last_scraped_at TIMESTAMP
            )
        ''')

        # Note: Legacy Posts and Comments tables removed in cleanup
        # Current bot uses per-group tables (Posts_Group_XXX) created dynamically

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS BotSettings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        conn.commit()
        logging.info(f"Database '{db_name}' initialized with Groups and Posts tables created or verified.")

    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    init_db() 