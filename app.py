import os
import sys
import cv2
import numpy as np
import base64
# Add root to path so we can import from 'database' folder
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_cors import CORS
from database import db_operations
from datetime import datetime
from functools import wraps

# Setup template folder path relative to this script
template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend', 'templates')
app = Flask(__name__, template_folder=template_dir)
CORS(app)
app.secret_key = 'vidyalaya_ai_secret_key_123' # Change this in production!

# Multi-Camera Engine Integration
from backend.camera_engine import EngineOrchestrator
import threading
import time
from backend import notifications
from database import cloud_config

# Initialize as None, will be set in main block to avoid multiprocessing loop on Windows
orchestrator = None

def background_attendance_monitor():
    """Periodically processes the queue from multiprocessing camera workers."""
    while True:
        if orchestrator:
            orchestrator.process_attendance_queue()
        time.sleep(1)

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'org_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index_page():
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    org_id = session['org_id']
    org_name = session['org_name']
    
    # Aaj ki date nikalna
    today = datetime.now().strftime('%Y-%m-%d')
    date_filter = request.args.get('date', today)
    
    # DB se data lana (SaaS filter)
    records = db_operations.get_all_attendance_today(org_id, date_filter)
    
    student_records = []
    teacher_records = []
    
    for row in records:
        role = row[2]
        if role and ('Teacher' in role or 'Sir' in role or 'Maam' in role):
            teacher_records.append(row)
        else:
            student_records.append(row)
            
    # Short Attendance List (SaaS filter)
    short_attendance = db_operations.get_short_attendance_students(org_id, threshold=75.0)
    
    cameras = db_operations.get_org_cameras(org_id)
    
    return render_template('dashboard.html', 
                           org_name=org_name,
                           student_records=student_records, 
                           teacher_records=teacher_records, 
                           date=date_filter,
                           short_attendance=short_attendance,
                           active_page='dashboard',
                           cameras=cameras)

@app.route('/critical')
@login_required
def critical_attendance():
    org_id = session['org_id']
    short_attendance = db_operations.get_short_attendance_students(org_id, threshold=75.0)
    return render_template('critical.html', short_attendance=short_attendance, active_page='critical')

@app.route('/registration')
@login_required
def registration_page():
    return render_template('registration.html', active_page='registration')

@app.route('/manage_users')
@login_required
def manage_users():
    org_id = session['org_id']
    users = db_operations.get_all_users(org_id)
    return render_template('manage_users.html', users=users, active_page='manage_users')

@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    import os
    import pickle
    
    # 1. Remove from names.txt
    names_file = 'names.txt'
    if os.path.exists(names_file):
        users_dict = {}
        with open(names_file, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) == 2:
                    users_dict[int(parts[0])] = parts[1]
        
        if user_id in users_dict:
            del users_dict[user_id]
            with open(names_file, 'w') as f:
                for uid, name in users_dict.items():
                    f.write(f"{uid},{name}\n")

    # 2. Remove from encodings.pkl
    encodings_file = os.path.join(os.path.dirname(__file__), 'encodings.pkl')
    if os.path.exists(encodings_file):
        with open(encodings_file, 'rb') as f:
            encodings = pickle.load(f)
        if user_id in encodings:
            del encodings[user_id]
            with open(encodings_file, 'wb') as f:
                pickle.dump(encodings, f)

    # 3. Remove from Database (SaaS filter)
    org_id = session['org_id']
    db_operations.delete_user(user_id, org_id)
    
    return f"User {user_id} deleted successfully", 200

@app.route('/manage_logs')
@login_required
def manage_logs():
    org_id = session['org_id']
    today = datetime.now().strftime('%Y-%m-%d')
    date_filter = request.args.get('date', today)
    records = db_operations.get_all_attendance_today(org_id, date_filter)
    return render_template('manage_logs.html', records=records, date=date_filter, active_page='manage_logs')

@app.route('/delete_attendance/<int:record_id>', methods=['POST'])
@login_required
def delete_attendance(record_id):
    # For extra security in SaaS, we should check if record belongs to org
    db_operations.delete_attendance_record(record_id)
    return f"Record {record_id} deleted", 200

@app.route('/live')
@login_required
def live_monitor():
    return render_template('live.html', active_page='live')

@app.route('/api/latest_logs')
@login_required
def latest_logs():
    from flask import jsonify
    org_id = session['org_id']
    today = datetime.now().strftime('%Y-%m-%d')
    records = db_operations.get_all_attendance_today(org_id, today)
    return jsonify([{
        'name': r[0],
        'time': r[1],
        'role': r[2],
        'class': r[3],
        'id': r[4]
    } for r in records])

@app.route('/register_school', methods=['GET', 'POST'])
def register_school():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not name or not email or not password:
            flash('All fields are required!', 'error')
            return redirect(url_for('register_school'))
            
        org_id = db_operations.register_organization(name, email, password)
        if org_id:
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Email or School Name already registered!', 'error')
            
    return render_template('register_school.html')

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    org_id = session['org_id']
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_camera':
            source = request.form.get('source')
            label = request.form.get('label')
            db_operations.add_org_camera(org_id, source, label)
            flash('Camera added successfully!', 'success')
            
        elif action == 'delete_camera':
            cam_id = request.form.get('camera_id')
            db_operations.delete_org_camera(cam_id, org_id)
            orchestrator.stop_camera(cam_id)
            flash('Camera removed.', 'success')
            
        elif action == 'update_threshold':
            threshold = request.form.get('threshold')
            db_operations.update_org_threshold(org_id, float(threshold))
            session['recognition_threshold'] = float(threshold)
            flash('AI Precision updated!', 'success')
            
        return redirect(url_for('settings'))
        
    cameras = db_operations.get_org_cameras(org_id)
    _, threshold = db_operations.get_org_settings(org_id)
    return render_template('settings.html', cameras=cameras, current_threshold=threshold, active_page='settings')

@app.route('/toggle_camera', methods=['POST'])
@login_required
def toggle_camera():
    global orchestrator
    if orchestrator is None:
        flash('System Engine is not initialized. Please restart the dashboard.', 'error')
        print("[CRITICAL] orchestrator is None in /toggle_camera route!")
        return redirect(url_for('dashboard'))

    org_id = session['org_id']
    cam_id = request.form.get('camera_id')
    new_status = int(request.form.get('status'))
    
    db_operations.update_camera_status(cam_id, org_id, new_status)
    
    if new_status == 0:
        orchestrator.stop_camera(cam_id)
        flash('Camera feed stopped.', 'success')
    else:
        # Fetch camera details to start it immediately
        cameras = db_operations.get_org_cameras(org_id)
        cam_info = next((c for c in cameras if str(c[0]) == str(cam_id)), None)
        if cam_info:
            _, source, label, _ = cam_info
            _, threshold = db_operations.get_org_settings(org_id)
            print(f"[INFO] Starting Camera {cam_id} ({label}) from Toggle. Source: {source}")
            orchestrator.start_camera(org_id, cam_id, source, threshold)
            flash(f'Camera {label} is now LIVE!', 'success')
        else:
            flash('Camera not found.', 'error')
            
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/start_monitoring', methods=['POST'])
@login_required
def start_monitoring():
    global orchestrator
    """Starts all active camera processes for the organization."""
    org_id = session['org_id']
    cameras = db_operations.get_org_cameras(org_id)
    _, threshold = db_operations.get_org_settings(org_id)
    
    count = 0
    for cam in cameras:
        cam_id, source, label, is_active = cam
        if is_active:
            orchestrator.start_camera(org_id, cam_id, source, threshold)
            count += 1
            
    flash(f'Successfully launched {count} camera feeds!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/stop_monitoring', methods=['POST'])
@login_required
def stop_monitoring():
    org_id = session['org_id']
    cameras = db_operations.get_org_cameras(org_id)
    for cam in cameras:
        orchestrator.stop_camera(cam[0])
    flash('All camera feeds stopped.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/reset_system', methods=['POST'])
@login_required
def reset_system():
    org_id = session['org_id']
    db_operations.reset_org_data(org_id)
    flash('System Reset Successful! All data has been cleared.', 'success')
    return redirect(url_for('settings'))
@app.route('/backup_data')
@login_required
def backup_data():
    org_id = session['org_id']
    data = db_operations.get_org_backup_data(org_id)
    import json
    from flask import Response
    
    json_data = json.dumps(data, indent=4)
    return Response(
        json_data,
        mimetype="application/json",
        headers={"Content-disposition": f"attachment; filename=VidyalayaAI_Backup_{session['org_name']}.json"}
    )
@app.route('/reports')
@login_required
def reports():
    org_id = session['org_id']
    stats = db_operations.get_student_stats(org_id)
    role_dist = db_operations.get_role_distribution(org_id)
    return render_template('reports.html', stats=stats, role_dist=role_dist, active_page='reports')

@app.route('/api/stats/trends')
@login_required
def get_stats_trends():
    org_id = session['org_id']
    days = request.args.get('days', 30, type=int)
    trends = db_operations.get_attendance_trends(org_id, days)
    return {"labels": [t[0] for t in trends], "data": [t[1] for t in trends]}

@app.route('/export_report')
@login_required
def export_report():
    import pandas as pd
    from fpdf import FPDF
    import io
    from flask import send_file
    
    org_id = session['org_id']
    format = request.args.get('format', 'excel')
    stats = db_operations.get_student_stats(org_id)
    
    df = pd.DataFrame(stats)
    df.columns = ['ID', 'Name', 'Class', 'Present Days', 'Attendance %']
    
    if format == 'excel':
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Attendance Report')
        output.seek(0)
        return send_file(
            output, 
            as_attachment=True, 
            download_name=f"Attendance_Report_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        # PDF Generation
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(190, 10, f"Attendance Report - {session['org_name']}", ln=True, align='C')
        pdf.set_font("Arial", "", 10)
        pdf.cell(190, 10, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align='C')
        pdf.ln(10)
        
        # Table Header
        pdf.set_font("Arial", "B", 10)
        pdf.cell(20, 10, "ID", 1)
        pdf.cell(60, 10, "Name", 1)
        pdf.cell(40, 10, "Class", 1)
        pdf.cell(30, 10, "Present", 1)
        pdf.cell(30, 10, "%", 1)
        pdf.ln()
        
        # Table Content
        pdf.set_font("Arial", "", 10)
        for s in stats:
            pdf.cell(20, 10, str(s['id']), 1)
            pdf.cell(60, 10, str(s['name']), 1)
            pdf.cell(40, 10, str(s['class']), 1)
            pdf.cell(30, 10, str(s['present_days']), 1)
            pdf.cell(30, 10, f"{s['percentage']}%", 1)
            pdf.ln()
            
        output = io.BytesIO(pdf.output())
        return send_file(
            output,
            as_attachment=True,
            download_name=f"Attendance_Report_{datetime.now().strftime('%Y-%m-%d')}.pdf",
            mimetype="application/pdf"
        )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('username') # Form field remains 'username' to avoid template changes
        password = request.form.get('password')
        
        org = db_operations.get_organization_by_login(email, password)
        if org:
            session['org_id'] = org[0]
            session['org_name'] = org[1]
            session['camera_index'] = org[2] # Store camera choice
            session['recognition_threshold'] = org[3] # Store AI threshold
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid Email or Password!', 'error')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ==========================================
# MOBILE APP API ROUTES (Merged)
# ==========================================
def require_api_token(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token or not token.startswith("Bearer "):
            return jsonify({"error": "Unauthorized"}), 401
        try:
            org_id = int(token.split(" ")[1])
            request.org_id = org_id
        except (ValueError, IndexError):
            return jsonify({"error": "Invalid Token"}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/app/login', methods=['POST'])
def mobile_login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    org = db_operations.get_organization_by_login(email, password)
    if org:
        org_id, org_name, camera_index, threshold = org
        return jsonify({
            "status": "success",
            "message": "Login Successful",
            "token": f"Bearer {org_id}",
            "org_name": org_name,
            "threshold": threshold
        }), 200
    return jsonify({"status": "error", "message": "Invalid credentials"}), 401

@app.route('/api/app/dashboard', methods=['GET'])
@require_api_token
def mobile_dashboard():
    org_id = request.org_id
    today = datetime.now().strftime('%Y-%m-%d')
    today_records = db_operations.get_all_attendance_today(org_id, today)
    stats = db_operations.get_student_stats(org_id)
    short_attendance = db_operations.get_short_attendance_students(org_id, 75.0)
    return jsonify({
        "status": "success",
        "date": today,
        "total_present_today": len(today_records),
        "total_students": len(stats),
        "critical_attendance_count": len(short_attendance),
        "recent_logs": [{"name": r[0], "time": r[1], "role": r[2], "class": r[3]} for r in today_records[:10]]
    }), 200

@app.route('/api/app/mark_attendance', methods=['POST'])
@require_api_token
def mobile_mark_attendance():
    import base64
    data = request.json
    base64_image = data.get('image')
    org_id = request.org_id
    if not base64_image:
        return jsonify({"status": "error", "message": "No image provided"}), 400
    try:
        img_data = base64.b64decode(base64_image.split(',')[1] if ',' in base64_image else base64_image)
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        signature = register_face.extract_face_signature(img)
        if signature is None:
            return jsonify({"status": "error", "message": "Face not detected properly. Move closer."}), 400
        known_encodings = register_face.load_encodings()
        _, threshold = db_operations.get_org_settings(org_id)
        known_ids = list(known_encodings.keys())
        known_sigs = list(known_encodings.values())
        if not known_sigs:
            return jsonify({"status": "error", "message": "Database is empty."}), 404
        distances = [np.linalg.norm(signature - ks) for ks in known_sigs]
        best_idx = np.argmin(distances)
        if distances[best_idx] < threshold:
            user_id = known_ids[best_idx]
            today = datetime.now().strftime('%Y-%m-%d')
            time_now = datetime.now().strftime('%H:%M:%S')
            user_name = register_face.names_dict.get(user_id) or "Unknown"
            marked = db_operations.mark_attendance_db(user_id, org_id, today, time_now)
            return jsonify({"status": "success", "message": f"Attendance marked for {user_name}!"}), 200
        return jsonify({"status": "error", "message": "Face not recognized."}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

from backend import register_face

@app.route('/register', methods=['POST'])
@login_required
def register():
    global orchestrator
    name = request.form.get('name')
    role = request.form.get('role')
    class_name = request.form.get('class_name', 'N/A')
    parent_phone = request.form.get('parent_phone', 'N/A')
    org_id = session['org_id']
    
    if not name or not role:
        return "Name and Role are required", 400
        
    # Check if any camera is already running (Conflict check)
    if orchestrator and orchestrator.active_processes:
        return "ERROR: Attendance Monitoring is active. Please 'STOP' all cameras from the Dashboard before registering new faces.", 405

    print(f"[INFO] Starting registration for: {name} ({role})")
    
    try:
        # Run the registration logic
        success = register_face.add_new_user_logic(name, role, class_name, org_id, parent_phone)
        
        if success:
            return f"Registration Success for {name}!", 200
        else:
            return "Registration Failed: Camera not found or canceled by user.", 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Internal Server Error: {str(e)}", 500

@app.route('/send_absence_notifications', methods=['POST'])
@login_required
def send_absence_notifications():
    global orchestrator
    org_id = session['org_id']
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 1. Get absent students
    absent_students = db_operations.get_absent_students(org_id, today)
    
    if not absent_students:
        flash('All students are present! No notifications needed.', 'info')
        return redirect(url_for('dashboard'))
        
    # 2. Trigger notifications
    success_count = 0
    fail_count = 0
    
    for student in absent_students:
        sid, name, phone, class_name = student
        # Skip if no phone number
        if not phone or phone == 'N/A':
            fail_count += 1
            continue
            
        success, _ = notifications.send_absence_notification(phone, name, class_name)
        if success:
            success_count += 1
        else:
            fail_count += 1
            
    flash(f'Absence Alerts: {success_count} sent successfully. {fail_count} failed/skipped.', 'success' if success_count > 0 else 'error')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    # Initialize Engine in the main process
    orchestrator = EngineOrchestrator()
    
    # Start monitor thread
    monitor_thread = threading.Thread(target=background_attendance_monitor, daemon=True)
    monitor_thread.start()

    app.config['TEMPLATES_AUTO_RELOAD'] = True
    print("[INFO] Dashboard Startup...")
    # debug=True with reloader can cause issues with multiprocessing on Windows
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
