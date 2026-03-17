import psycopg2
from database import cloud_config

def test_conn():
    print(f"Testing Supabase connection...")
    try:
        conn = psycopg2.connect(cloud_config.DB_CONNECTION_STRING, connect_timeout=5)
        print("SUCCESS: Connected to Supabase!")
        conn.close()
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    test_conn()
