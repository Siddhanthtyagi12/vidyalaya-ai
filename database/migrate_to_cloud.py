import sqlite3
import psycopg2
import cloud_config

def migrate_data():
    if not cloud_config.USE_CLOUD or "[YOUR-PASSWORD]" in cloud_config.DB_CONNECTION_STRING:
        print("[ERROR] Please set your actual Supabase password in cloud_config.py and set USE_CLOUD = True first!")
        return

    print("[INFO] Migration shuru ho rahi hai: Local SQLite -> Supabase Cloud...")
    
    # Connections
    local_conn = sqlite3.connect('school_data.db')
    cloud_conn = psycopg2.connect(cloud_config.DB_CONNECTION_STRING)
    
    local_cur = local_conn.cursor()
    cloud_cur = cloud_conn.cursor()
    
    tables = ['Organizations', 'Users', 'Cameras', 'Attendance']
    
    for table in tables:
        print(f"[MIGRATING] Table: {table}...")
        local_cur.execute(f"SELECT * FROM {table}")
        rows = local_cur.fetchall()
        
        if not rows:
            print(f"  - No data in {table}, skipping.")
            continue
            
        # PostgreSQL table names are lowercase
        cloud_table = table.lower()
        
        # Explicit mapping due to schema differences
        if table == 'Organizations':
            # SQLite: id, name, email, password, created_at, camera_index, recognition_threshold
            # Cloud (organizations): id, name, email, password, camera_index, recognition_threshold, created_at
            mapped_rows = [(r[0], r[1], r[2], r[3], r[5], r[6], r[4]) for r in rows]
            columns = "(id, name, email, password, camera_index, recognition_threshold, created_at)"
        elif table == 'Users':
            # SQLite: id, name, role, class_name, org_id, parent_phone
            # Cloud (users): id, name, role, class_name, parent_phone, org_id
            mapped_rows = [(r[0], r[1], r[2], r[3], r[5], r[4]) for r in rows]
            columns = "(id, name, role, class_name, parent_phone, org_id)"
        elif table == 'Attendance':
            # SQLite Actual: record_id, user_id, date, time, status, org_id
            # Cloud (attendance): record_id, user_id, org_id, date, time, status
            mapped_rows = [(r[0], r[1], r[5], r[2], r[3], r[4]) for r in rows]
            columns = "(record_id, user_id, org_id, date, time, status)"
        else:
            mapped_rows = rows
            columns = "" 
            
        rows = mapped_rows
        col_count = len(rows[0])
        placeholders = ",".join(["%s"] * col_count)
        
        # Clear existing data in cloud
        cloud_cur.execute(f"TRUNCATE TABLE {cloud_table} CASCADE")
        
        # Insert into cloud
        query = f"INSERT INTO {cloud_table} {columns} VALUES ({placeholders})"
        cloud_cur.executemany(query, rows)
        print(f"  - Successfully moved {len(rows)} records to {cloud_table}.")

    cloud_conn.commit()
    print("\n[SUCCESS] Mubarak ho! Aapka saara purana data ab Cloud (Supabase) par hai!")
    
    local_conn.close()
    cloud_conn.close()

if __name__ == "__main__":
    migrate_data()
