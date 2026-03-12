import os
import cv2
import numpy as np
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
from functools import wraps

import sys
# Add root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import your existing DB logic
from database import db_operations

# We can reuse the Mediapipe logic from register_face.py
from backend import register_face

app = Flask(__name__)
CORS(app)

# Basic token authentication decorator (for Mobile App security)
def require_api_token(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        # In a real app, use JWT. For MVP, we pass org_id in header for simplicity.
        if not token or not token.startswith("Bearer "):
            return jsonify({"error": "Unauthorized"}), 401
        
        try:
            org_id = int(token.split(" ")[1])
            request.org_id = org_id
        except ValueError:
            return jsonify({"error": "Invalid Token"}), 401
            
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# 1. MOBILE LOGIN ENDPOINT
# ==========================================
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
            "token": f"Bearer {org_id}",  # Simple auth token for MVP
            "org_name": org_name,
            "threshold": threshold
        }), 200
    else:
        return jsonify({"status": "error", "message": "Invalid credentials"}), 401


# ==========================================
# 2. DASHBOARD DATA ENDPOINT
# ==========================================
@app.route('/api/app/dashboard', methods=['GET'])
@require_api_token
def mobile_dashboard():
    org_id = request.org_id
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Get attendance data
    today_records = db_operations.get_all_attendance_today(org_id, today)
    stats = db_operations.get_student_stats(org_id)
    short_attendance = db_operations.get_short_attendance_students(org_id, 75.0)
    
    return jsonify({
        "status": "success",
        "date": today,
        "total_present_today": len(today_records),
        "total_students": len(stats),
        "critical_attendance_count": len(short_attendance),
        "recent_logs": [
            {"name": r[0], "time": r[1], "role": r[2], "class": r[3]} for r in today_records[:10]
        ]
    }), 200


# ==========================================
# 3. CLOUD AI ACCURACY (Attendace Marking)
# ==========================================
@app.route('/api/app/mark_attendance', methods=['POST'])
@require_api_token
def mobile_mark_attendance():
    """
    Mobile phone sends base64 image string here.
    Server processes it and marks attendance.
    """
    data = request.json
    base64_image = data.get('image')
    org_id = request.org_id
    
    if not base64_image:
        return jsonify({"status": "error", "message": "No image provided"}), 400
        
    try:
        # Decode base64 to OpenCV format
        img_data = base64.b64decode(base64_image.split(',')[1] if ',' in base64_image else base64_image)
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # 1. Extract Face Signature (Server AI working)
        signature = register_face.extract_face_signature(img)
        
        if signature is None:
            return jsonify({"status": "error", "message": "Face not detected properly. Move closer."}), 400
            
        # 2. Compare against known encodings
        known_encodings = register_face.load_encodings()
        _, _, _, threshold = db_operations.get_org_settings(org_id)
        
        known_ids = list(known_encodings.keys())
        known_sigs = list(known_encodings.values())
        
        if not known_sigs:
            return jsonify({"status": "error", "message": "Database is empty. Register students first."}), 404
            
        distances = [np.linalg.norm(signature - ks) for ks in known_sigs]
        best_idx = np.argmin(distances)
        min_dist = distances[best_idx]
        
        if min_dist < threshold:
            user_id = known_ids[best_idx]
            today = datetime.now().strftime('%Y-%m-%d')
            time_now = datetime.now().strftime('%H:%M:%S')
            
            # Fetch Name
            user_name = register_face.names_dict.get(user_id) or "Unknown"
            
            # 3. Save to DB
            marked = db_operations.mark_attendance_db(user_id, org_id, today, time_now)
            
            if marked:
                return jsonify({"status": "success", "message": f"Attendance marked for {user_name}!"}), 200
            else:
                return jsonify({"status": "success", "message": f"{user_name} is already marked present today!"}), 200
        else:
            return jsonify({"status": "error", "message": "Face not recognized. Not in Database."}), 401
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    print("[INFO] Cloud API Server is running on Port 8000 for Mobile Apps...")
    app.run(host='0.0.0.0', port=8000, debug=True)
