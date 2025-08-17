import sqlite3

def migrate_database():
    try:
        conn = sqlite3.connect('gym.db')
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(members)")
        columns = [col[1] for col in cursor.fetchall()]
        print("Current columns in members:", columns)
        
        if 'location' not in columns:
            cursor.execute("ALTER TABLE members ADD COLUMN location TEXT")
            print("Added location column")
        
        if 'total_fee' not in columns:
            cursor.execute("ALTER TABLE members ADD COLUMN total_fee REAL NOT NULL DEFAULT 0")
            print("Added total_fee column")
        
        if 'is_active' not in columns:
            cursor.execute("ALTER TABLE members ADD COLUMN is_active BOOLEAN DEFAULT 1")
            print("Added is_active column")
        
        if 'updated_at' not in columns:
            cursor.execute("ALTER TABLE members ADD COLUMN updated_at TEXT")
            print("Added updated_at column")
        
        cursor.execute("PRAGMA table_info(members)")
        expiry_info = next(col for col in cursor.fetchall() if col[1] == 'expiry_date')
        if not expiry_info[3]:
            print("Making expiry_date NOT NULL (data may need review)")
            cursor.execute("UPDATE members SET expiry_date='9999-12-31' WHERE expiry_date IS NULL")
        
        cursor.execute("PRAGMA table_info(payments)")
        payment_columns = [col[1] for col in cursor.fetchall()]
        print("Current columns in payments:", payment_columns)
        
        if 'updated_at' not in payment_columns:
            cursor.execute("ALTER TABLE payments ADD COLUMN updated_at TEXT")
            print("Added updated_at column to payments")
        
        try:
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_member_month ON payments(member_id, month)")
            print("Added unique index on payments(member_id, month)")
        except sqlite3.OperationalError:
            print("Unique index already exists or table needs review")
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cnic ON members(cnic)")
        print("Ensured cnic index exists")
        
        conn.commit()
        print("Database migration completed successfully!")
        
    except sqlite3.Error as e:
        print(f"Migration failed: {str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()