import sqlite3
from datetime import datetime

def initialize_database(db_path='gym.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Members table with user_id as TEXT PRIMARY KEY and photo_path
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS members (
        user_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        contact TEXT NOT NULL,
        cnic TEXT UNIQUE NOT NULL,
        location TEXT,
        designation TEXT,
        join_date TEXT NOT NULL,
        expiry_date TEXT NOT NULL,
        sport_category TEXT NOT NULL,
        membership_type TEXT NOT NULL CHECK(membership_type IN ('15-day', '30-day')),
        has_treadmill INTEGER NOT NULL DEFAULT 0,
        base_fee REAL NOT NULL,
        total_fee REAL NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        updated_at TEXT NOT NULL,
        photo_path TEXT
    )
    ''')
    
    # Index on cnic for faster searches
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_cnic ON members(cnic)
    ''')
    
    # Payments table with user_id referencing members(user_id)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        amount REAL NOT NULL,
        payment_date TEXT NOT NULL,
        month TEXT NOT NULL,
        period TEXT,  -- NULL for 30-day, 'first_half'/'second_half' for 15-day
        updated_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES members(user_id),
        UNIQUE(user_id, month, period)
    )
    ''')
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    initialize_database()
    print("Database initialized successfully!")