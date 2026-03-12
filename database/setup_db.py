import sqlite3
import os

# Yeh scipt sirf ek baar chalani hai, ye aapke school ka database banayegi

db_file = "school_data.db"

def setup_database():
    print("[INFO] Database Setup ho raha hai...")
    
    # 1. Database se judna (Nahi hai to ban jayega)
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # 1. Organizations Table (SaaS Tenants)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Organizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insert default organization to avoid breaking existing data
    cursor.execute("INSERT OR IGNORE INTO Organizations (id, name, email, password) VALUES (1, 'Vidyalaya Main', 'admin@vidyalaya.ai', 'admin123')")

    # 2. 'Users' Table banana (Bacho/Teachers ka record)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT DEFAULT 'Student',
            class_name TEXT DEFAULT 'N/A',
            org_id INTEGER DEFAULT 1,
            FOREIGN KEY(org_id) REFERENCES Organizations(id)
        )
    ''')
    
    # 3. 'Attendance' Table banana (Roz ki haazri)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Attendance (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            org_id INTEGER DEFAULT 1,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            status TEXT DEFAULT 'Present',
            FOREIGN KEY(user_id) REFERENCES Users(id),
            FOREIGN KEY(org_id) REFERENCES Organizations(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"[SUCCESS] Database '{db_file}' me Tables ban gayi hain!")

if __name__ == "__main__":
    setup_database()
