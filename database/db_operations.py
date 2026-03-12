import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
try:
    from database import cloud_config
except ImportError:
    import cloud_config

def connect_db():
    if cloud_config.USE_CLOUD:
        try:
            conn = psycopg2.connect(cloud_config.DB_CONNECTION_STRING)
            return conn
        except Exception as e:
            print(f"[ERROR] Cloud DB Connection Failed: {e}")
            print("[INFO] Falling back to Local SQLite...")
            return sqlite3.connect('school_data.db')
    else:
        return sqlite3.connect('school_data.db')

def get_placeholder():
    return "%s" if cloud_config.USE_CLOUD else "?"

def get_table(name):
    """Postgres tables are lowercase in Supabase schema."""
    if cloud_config.USE_CLOUD:
        return name.lower()
    return name

def add_user(user_id, name, org_id=1, role="Student", class_name="N/A", parent_phone="N/A"):
    conn = connect_db()
    cursor = conn.cursor()
    q = get_placeholder()
    tbl = get_table("Users")
    
    try:
        if cloud_config.USE_CLOUD:
            cursor.execute(f"INSERT INTO {tbl} (id, name, org_id, role, class_name, parent_phone) VALUES ({q}, {q}, {q}, {q}, {q}, {q}) ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, role=EXCLUDED.role, class_name=EXCLUDED.class_name, org_id=EXCLUDED.org_id, parent_phone=EXCLUDED.parent_phone", 
                           (user_id, name, org_id, role, class_name, parent_phone))
        else:
            cursor.execute(f"INSERT INTO {tbl} (id, name, org_id, role, class_name, parent_phone) VALUES ({q}, {q}, {q}, {q}, {q}, {q})", 
                           (user_id, name, org_id, role, class_name, parent_phone))
        conn.commit()
    except (sqlite3.IntegrityError, psycopg2.errors.UniqueViolation if cloud_config.USE_CLOUD else Exception):
        if not cloud_config.USE_CLOUD:
            cursor.execute(f"UPDATE {tbl} SET name={q}, role={q}, class_name={q}, org_id={q}, parent_phone={q} WHERE id={q}", 
                        (name, role, class_name, org_id, parent_phone, user_id))
            conn.commit()
    finally:
        conn.close()

def mark_attendance_db(user_id, org_id, date_str, time_str):
    conn = connect_db()
    cursor = conn.cursor()
    q = get_placeholder()
    tbl = get_table("Attendance")
    try:
        # Check if already marked today for this org
        cursor.execute(f"SELECT * FROM {tbl} WHERE user_id={q} AND org_id={q} AND date={q}", (user_id, org_id, date_str))
        if not cursor.fetchone():
            cursor.execute(f"INSERT INTO {tbl} (user_id, org_id, date, time, status) VALUES ({q}, {q}, {q}, {q}, 'Present')", (user_id, org_id, date_str, time_str))
            conn.commit()
            return True
        return False
    finally:
        conn.close()

def get_all_users(org_id):
    conn = connect_db()
    cursor = conn.cursor()
    q = get_placeholder()
    tbl = get_table("Users")
    cursor.execute(f"SELECT id, name, role, class_name, parent_phone FROM {tbl} WHERE org_id={q} ORDER BY name", (org_id,))
    users = cursor.fetchall()
    conn.close()
    return users

def get_all_attendance_today(org_id, date_str):
    conn = connect_db()
    cursor = conn.cursor()
    q = get_placeholder()
    a_tbl = get_table("Attendance")
    u_tbl = get_table("Users")
    cursor.execute(f'''
        SELECT {u_tbl}.name, {a_tbl}.time, {u_tbl}.role, {u_tbl}.class_name, {a_tbl}.record_id
        FROM {a_tbl} 
        JOIN {u_tbl} ON {a_tbl}.user_id = {u_tbl}.id 
        WHERE {a_tbl}.date = {q} AND {a_tbl}.org_id = {q}
    ''', (date_str, org_id))
    data = cursor.fetchall()
    conn.close()
    return data

def delete_attendance_record(record_id):
    conn = connect_db()
    cursor = conn.cursor()
    q = get_placeholder()
    tbl = get_table("Attendance")
    cursor.execute(f"DELETE FROM {tbl} WHERE record_id={q}", (record_id,))
    conn.commit()
    conn.close()

def get_short_attendance_students(org_id, threshold=75.0):
    conn = connect_db()
    cursor = conn.cursor()
    q = get_placeholder()
    a_tbl = get_table("Attendance")
    u_tbl = get_table("Users")
    
    # Total unique dates in Attendance table for this org
    cursor.execute(f"SELECT COUNT(DISTINCT date) FROM {a_tbl} WHERE org_id={q}", (org_id,))
    row = cursor.fetchone()
    total_days = row[0] if row else 0
    
    if total_days == 0:
        conn.close()
        return []
        
    # Student level stats
    cursor.execute(f'''
        SELECT {u_tbl}.id, {u_tbl}.name, {u_tbl}.class_name, COUNT(DISTINCT {a_tbl}.date) as present_days
        FROM {u_tbl}
        LEFT JOIN {a_tbl} ON {u_tbl}.id = {a_tbl}.user_id AND {a_tbl}.org_id = {q}
        WHERE {u_tbl}.role = 'Student' AND {u_tbl}.org_id = {q}
        GROUP BY {u_tbl}.id, {u_tbl}.name, {u_tbl}.class_name
    ''', (org_id, org_id))
    
    students = cursor.fetchall()
    short_attendance = []
    
    for student_id, name, class_name, present_days in students:
        percentage = (present_days / total_days) * 100
        if percentage < threshold:
            short_attendance.append({
                'id': student_id,
                'name': name,
                'class_name': class_name,
                'percentage': round(percentage, 1),
                'present_days': present_days,
                'total_days': total_days
            })
            
    conn.close()
    return short_attendance

def delete_user(user_id, org_id):
    conn = connect_db()
    cursor = conn.cursor()
    q = get_placeholder()
    u_tbl = get_table("Users")
    a_tbl = get_table("Attendance")
    cursor.execute(f"DELETE FROM {u_tbl} WHERE id={q} AND org_id={q}", (user_id, org_id))
    cursor.execute(f"DELETE FROM {a_tbl} WHERE user_id={q} AND org_id={q}", (user_id, org_id))
    conn.commit()
    conn.close()

def register_organization(name, email, password):
    conn = connect_db()
    cursor = conn.cursor()
    q = get_placeholder()
    tbl = get_table("Organizations")
    try:
        cursor.execute(f"INSERT INTO {tbl} (name, email, password) VALUES ({q}, {q}, {q})", (name, email, password))
        conn.commit()
        if cloud_config.USE_CLOUD:
            # Postgres doesn't have lastrowid, use RETURNING if needed or query
            cursor.execute(f"SELECT id FROM {tbl} WHERE email={q}", (email,))
            return cursor.fetchone()[0]
        return cursor.lastrowid
    except Exception:
        return None
    finally:
        conn.close()

def get_organization_by_login(email, password):
    conn = connect_db()
    cursor = conn.cursor()
    q = get_placeholder()
    tbl = get_table("Organizations")
    # Using LOWER() for case-insensitive email matching
    cursor.execute(f"SELECT id, name, camera_index, recognition_threshold FROM {tbl} WHERE LOWER(email)=LOWER({q}) AND password={q}", (email, password))
    org = cursor.fetchone()
    conn.close()
    return org

def update_org_camera(org_id, camera_index):
    conn = connect_db()
    cursor = conn.cursor()
    q = get_placeholder()
    tbl = get_table("Organizations")
    cursor.execute(f"UPDATE {tbl} SET camera_index={q} WHERE id={q}", (camera_index, org_id))
    conn.commit()
    conn.close()

def update_org_threshold(org_id, threshold):
    conn = connect_db()
    cursor = conn.cursor()
    q = get_placeholder()
    tbl = get_table("Organizations")
    cursor.execute(f"UPDATE {tbl} SET recognition_threshold={q} WHERE id={q}", (threshold, org_id))
    conn.commit()
    conn.close()

def get_org_settings(org_id):
    conn = connect_db()
    cursor = conn.cursor()
    q = get_placeholder()
    tbl = get_table("Organizations")
    cursor.execute(f"SELECT camera_index, recognition_threshold FROM {tbl} WHERE id={q}", (org_id,))
    row = cursor.fetchone()
    conn.close()
    return row if row else (0, 1.2)

def get_org_camera_index(org_id):
    """Backward compatibility wrapper. Prioritizes Cameras table."""
    conn = connect_db()
    cursor = conn.cursor()
    q = get_placeholder()
    tbl = get_table("Cameras")
    # Try getting first active camera from new table
    cursor.execute(f"SELECT source FROM {tbl} WHERE org_id={q} AND is_active=1 LIMIT 1", (org_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        source = row[0]
        try:
            return int(source) # USB camera index
        except ValueError:
            return source # RTSP URL
            
    # Fallback to organization default
    settings = get_org_settings(org_id)
    source = settings[0]
    try:
        return int(source)
    except (ValueError, TypeError):
        return source

def reset_org_data(org_id):
    """Permanently deletes all users and attendance for an organization."""
    conn = connect_db()
    cursor = conn.cursor()
    q = get_placeholder()
    a_tbl = get_table("Attendance")
    u_tbl = get_table("Users")
    cursor.execute(f"DELETE FROM {a_tbl} WHERE org_id={q}", (org_id,))
    cursor.execute(f"DELETE FROM {u_tbl} WHERE org_id={q}", (org_id,))
    conn.commit()
    conn.close()

def get_org_backup_data(org_id):
    """Retrieves all users and attendance for export."""
    conn = connect_db()
    cursor = conn.cursor()
    q = get_placeholder()
    u_tbl = get_table("Users")
    a_tbl = get_table("Attendance")
    
    # Get users
    cursor.execute(f"SELECT id, name, role, class_name FROM {u_tbl} WHERE org_id={q}", (org_id,))
    users = cursor.fetchall()
    
    # Get attendance
    cursor.execute(f"SELECT user_id, date, time, status FROM {a_tbl} WHERE org_id={q}", (org_id,))
    attendance = cursor.fetchall()
    
    conn.close()
    return {"users": users, "attendance": attendance}

def get_org_cameras(org_id):
    """Fetches all cameras for an organization."""
    conn = connect_db()
    cursor = conn.cursor()
    q = get_placeholder()
    tbl = get_table("Cameras")
    cursor.execute(f"SELECT id, source, label, is_active FROM {tbl} WHERE org_id={q}", (org_id,))
    cameras = cursor.fetchall()
    conn.close()
    return cameras

def add_org_camera(org_id, source, label="New Camera"):
    """Adds a new camera source (index or RTSP)."""
    conn = connect_db()
    cursor = conn.cursor()
    q = get_placeholder()
    tbl = get_table("Cameras")
    cursor.execute(f"INSERT INTO {tbl} (org_id, source, label) VALUES ({q}, {q}, {q})", (org_id, source, label))
    conn.commit()
    conn.close()

def delete_org_camera(camera_id, org_id):
    """Deletes a specific camera for an organization."""
    conn = connect_db()
    cursor = conn.cursor()
    q = get_placeholder()
    tbl = get_table("Cameras")
    cursor.execute(f"DELETE FROM {tbl} WHERE id={q} AND org_id={q}", (camera_id, org_id))
    conn.commit()
    conn.close()

def update_camera_status(camera_id, org_id, is_active):
    """Toggles camera active status."""
    conn = connect_db()
    cursor = conn.cursor()
    q = get_placeholder()
    tbl = get_table("Cameras")
    cursor.execute(f"UPDATE {tbl} SET is_active={q} WHERE id={q} AND org_id={q}", (int(is_active), camera_id, org_id))
    conn.commit()
    conn.close()

def get_attendance_trends(org_id, days=30):
    """Returns attendance count per day for the last X days."""
    conn = connect_db()
    cursor = conn.cursor()
    q = get_placeholder()
    a_tbl = get_table("Attendance")
    cursor.execute(f'''
        SELECT date, COUNT(DISTINCT user_id) 
        FROM {a_tbl} 
        WHERE org_id={q} 
        GROUP BY date 
        ORDER BY date DESC 
        LIMIT {q}
    ''', (org_id, days))
    trends = cursor.fetchall()
    conn.close()
    return trends[::-1] # Return in chronological order

def get_student_stats(org_id):
    """Calculates attendance percentage and total present days per student."""
    conn = connect_db()
    cursor = conn.cursor()
    q = get_placeholder()
    a_tbl = get_table("Attendance")
    u_tbl = get_table("Users")
    
    # 1. Get total distinct attendance days for the org (benchmark)
    cursor.execute(f"SELECT COUNT(DISTINCT date) FROM {a_tbl} WHERE org_id={q}", (org_id,))
    total_school_days_row = cursor.fetchone()
    total_school_days = (total_school_days_row[0] if total_school_days_row else 1) or 1
    
    # 2. Get attendance count per student
    like_pattern = "%%Teacher%%" if cloud_config.USE_CLOUD else "%Teacher%"
    cursor.execute(f'''
        SELECT u.id, u.name, u.class_name, COUNT(DISTINCT a.date) as present_days
        FROM {u_tbl} u
        LEFT JOIN {a_tbl} a ON u.id = a.user_id AND a.org_id = {q}
        WHERE u.org_id={q} AND u.role NOT LIKE {q}
        GROUP BY u.id, u.name, u.class_name
    ''', (org_id, org_id, like_pattern))
    
    stats = []
    for row in cursor.fetchall():
        uid, name, cls, present = row
        percentage = round((present / total_school_days) * 100, 1)
        stats.append({
            'id': uid,
            'name': name,
            'class': cls,
            'present_days': present,
            'percentage': percentage
        })
    
    conn.close()
    return stats

def get_role_distribution(org_id):
    """Returns breakdown of Students vs Teachers present today."""
    today = datetime.now().strftime('%Y-%m-%d')
    conn = connect_db()
    cursor = conn.cursor()
    q = get_placeholder()
    a_tbl = get_table("Attendance")
    u_tbl = get_table("Users")
    cursor.execute(f'''
        SELECT u.role, COUNT(DISTINCT a.user_id)
        FROM {a_tbl} a
        JOIN {u_tbl} u ON a.user_id = u.id
        WHERE a.org_id={q} AND a.date={q}
        GROUP BY u.role
    ''', (org_id, today))
    dist = cursor.fetchall()
    conn.close()
    return dist

def get_absent_students(org_id, date_str):
    """Returns list of students who have not marked attendance for a given date."""
    conn = connect_db()
    cursor = conn.cursor()
    q = get_placeholder()
    a_tbl = get_table("Attendance")
    u_tbl = get_table("Users")
    cursor.execute(f'''
        SELECT id, name, parent_phone, class_name
        FROM {u_tbl} 
        WHERE org_id={q} AND role='Student' AND id NOT IN (
            SELECT user_id FROM {a_tbl} WHERE org_id={q} AND date={q}
        )
    ''', (org_id, org_id, date_str))
    absent = cursor.fetchall()
    conn.close()
    return absent
