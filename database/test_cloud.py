import sys
import os
# Add root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import db_operations
from database import cloud_config
import psycopg2
import sqlite3

def test_cloud_flow():
    print(f"[DIAGNOSTIC] USE_CLOUD: {cloud_config.USE_CLOUD}")
    print(f"[DIAGNOSTIC] DB_CONNECTION_STRING contains password: {'YES' if 'siddhant' in cloud_config.DB_CONNECTION_STRING else 'NO'}")
    
    try:
        conn = db_operations.connect_db()
        # Check type of connection
        if isinstance(conn, sqlite3.Connection):
            print("[ALERT] connect_db() returned a SQLITE connection! (Fallback happened)")
            conn.close()
            return
        
        print("[SUCCESS] connect_db() returned a POSTGRES connection.")
        
        # Try a test insert
        print("[INFO] Attempting test insert into cloud...")
        db_operations.add_user(999, "Cloud Test User", org_id=1)
        print("[SUCCESS] Test user (ID 999) added to DB.")
        
        # Verify
        cur = conn.cursor()
        cur.execute("SELECT name FROM users WHERE id=999")
        row = cur.fetchone()
        if row:
            print(f"[VERIFIED] Found user in Cloud DB: {row[0]}")
            # Clean up
            # cur.execute("DELETE FROM users WHERE id=999")
            # conn.commit()
        else:
            print("[ERROR] User was NOT found in Cloud DB after insertion!")
            
        conn.close()
    except Exception as e:
        print(f"[CRITICAL ERROR] Diagnostic failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_cloud_flow()
