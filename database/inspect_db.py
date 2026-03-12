import sqlite3
import pandas as pd

def inspect_db():
    conn = sqlite3.connect('school_data.db')
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall() if t[0] != 'sqlite_sequence']
    
    print("=== Vidyalaya AI Local Database Inspection ===\n")
    
    for table in tables:
        print(f"--- Table: {table} ---")
        try:
            df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
            if df.empty:
                print("(Empty Table)")
            else:
                print(df.head(10).to_string(index=False))
        except Exception as e:
            print(f"Error reading table {table}: {e}")
        print("\n")
    
    conn.close()

if __name__ == "__main__":
    inspect_db()
