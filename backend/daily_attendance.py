import cv2
import numpy as np
import os
import pickle
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions, RunningMode
from datetime import datetime
import os

# Suppress MediaPipe/TensorFlow warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# Hackathon Winner Standard: MediaPipe TASKS (CNN) + Blink Liveness
# Optimized for Windows Python 3.13!

# Task Setup
model_path = os.path.join(os.path.dirname(__file__), 'face_landmarker.task')
base_options = python.BaseOptions(model_asset_path=model_path)
options = FaceLandmarkerOptions(
    base_options=base_options,
    running_mode=RunningMode.IMAGE,
    num_faces=5
)
landmarker = FaceLandmarker.create_from_options(options)

names_file = os.path.join(os.path.dirname(__file__), 'names.txt')
encodings_file = os.path.join(os.path.dirname(__file__), 'encodings.pkl')

names_dict = {}
if os.path.exists(names_file):
    with open(names_file, 'r') as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) == 2:
                names_dict[int(parts[0])] = parts[1]

import sys
# Add root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import db_operations

def load_encodings():
    if os.path.exists(encodings_file):
        with open(encodings_file, 'rb') as f:
            return pickle.load(f)
    return {}

def calculate_ear(landmarks, eye_indices):
    pts = [np.array([landmarks[i].x, landmarks[i].y]) for i in eye_indices]
    A = np.linalg.norm(pts[1] - pts[5])
    B = np.linalg.norm(pts[2] - pts[4])
    C = np.linalg.norm(pts[0] - pts[3])
    ear = (A + B) / (2.0 * C)
    return ear

# Global set to track attendance in-memory for the current session to avoid redundant DB/CSV hits
marked_today_cache = set()

def markAttendance(user_id, name, org_id=1):
    now = datetime.now()
    dateString = now.strftime('%Y-%m-%d')
    dtString = now.strftime('%H:%M:%S')
    
    # 1. Check in-memory cache first
    cache_key = f"{user_id}_{dateString}"
    if cache_key in marked_today_cache:
        return False

    # 2. If not in cache, mark in DB
    print(f"[INFO] Marking attendance for {name} (ID: {user_id})...")
    
    success = db_operations.mark_attendance_db(user_id, org_id, dateString, dtString)
    
    if success:
        # Update CSV
        csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'Attendance.csv')
        with open(csv_path, 'a+') as f:
            f.writelines(f'{name},{dtString},{dateString}\n')
        
        # Update Cache
        marked_today_cache.add(cache_key)
        print(f"[ATTENDANCE] -> {name} ({dtString}) - Liveness Verified")
        return True
    else:
        # If DB says already marked, update cache to avoid future checks
        marked_today_cache.add(cache_key)
        return False

def run_attendance(org_id=1):
    # Fetch settings from DB
    camera_idx, rec_threshold = db_operations.get_org_settings(org_id)
    known_encodings_dict = load_encodings()
    
    if not known_encodings_dict:
        print("\n[WARNING] Koi users registered nahi hain. Sabhi log 'Unknown' mark honge.")

    known_ids = list(known_encodings_dict.keys())
    known_signatures = list(known_encodings_dict.values())
    
    # Use the dynamic threshold from DB
    RECOGNITION_THRESHOLD = rec_threshold 
    print(f"[INFO] Initializing Camera {camera_idx} with AI Threshold: {RECOGNITION_THRESHOLD}")
    
    cap = cv2.VideoCapture(camera_idx, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"\n[ERROR] Camera {camera_idx} is required but could not be opened.")
        print("-> CHECK: Is the Dashboard currently running Live Monitoring? If yes, please 'STOP' all cameras from the Web Dashboard first!")
        input("\nPress ENTER to exit...")
        return
        
    ret, _ = cap.read()
    if not ret:
        print(f"\n[ERROR] Camera {camera_idx} opened but cannot read frames.")
        print("-> CHECK: The camera might be locked by another Python process.")
        input("\nPress ENTER to exit...")
        cap.release()
        return
        
    blink_counters = {} # {id: {'count': 0, 'blinked': False}}
    identity_buffer = {} # {id: frame_count} to ensure stability
    
    # MediaPipe Mesh Indices for EAR
    LEFT_EYE = [33, 160, 158, 133, 153, 144]
    RIGHT_EYE = [362, 385, 387, 263, 373, 380]
    EAR_THRESHOLD = 0.18
    RECOGNITION_THRESHOLD = 1.2 # Tighter scientific threshold
    STABILITY_FRAMES = 5
    
    print("\n[INFO] MediaPipe Tasks Attendance System Active!")
    print("[INFO] Accuracy: Multi-Norm (Scientific) | Stability: 5-Frame Confirmation")

    while True:
        ret, img = cap.read()
        if not ret: 
            print("\n[ERROR] Lost connection to camera unexpectedly. Exiting.")
            break
        
        # Convert to MediaPipe Image
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        detection_result = landmarker.detect(mp_image)
        
        if detection_result.face_landmarks:
            for face_landmarks in detection_result.face_landmarks:
                # 1. LANDMARK EXTRACTION
                sig = []
                for l in face_landmarks:
                    sig.extend([l.x, l.y, l.z])
                sig = np.array(sig)
                
                # 2. SCIENTIFIC NORMALIZATION (Zero-Mean & Unit-Norm)
                sig = sig - np.mean(sig)
                norm = np.linalg.norm(sig)
                if norm > 0:
                    sig = sig / norm
                current_sig = sig
                
                if known_signatures:
                    # 3. FACE MATCHING (Euclidean Distance)
                    distances = [np.linalg.norm(current_sig - ks) for ks in known_signatures]
                    best_match_idx = np.argmin(distances)
                    
                    if distances[best_match_idx] < RECOGNITION_THRESHOLD:
                        match_id = known_ids[best_match_idx]
                        name = names_dict.get(match_id, "Unknown")
                        
                        # 4. TEMPORAL STABILITY (5 Consecutive Frames)
                        identity_buffer[match_id] = identity_buffer.get(match_id, 0) + 1
                        
                        if identity_buffer[match_id] >= STABILITY_FRAMES:
                            color = (0, 165, 255) # Orange (Ready for blink)
                            status_text = f"{name}: Please Blink"
                            
                            # 5. EYE BLINK DETECTION (Liveness)
                            ear = (calculate_ear(face_landmarks, LEFT_EYE) + 
                                   calculate_ear(face_landmarks, RIGHT_EYE)) / 2.0
                            
                            if match_id not in blink_counters:
                                blink_counters[match_id] = {'count': 0, 'blinked': False}
                            
                            if ear < EAR_THRESHOLD:
                                blink_counters[match_id]['count'] += 1
                            else:
                                if blink_counters[match_id]['count'] >= 2:
                                    blink_counters[match_id]['blinked'] = True
                                blink_counters[match_id]['count'] = 0
                            
                            if blink_counters[match_id]['blinked']:
                                # 6. MARK ATTENDANCE
                                if markAttendance(match_id, name, org_id=1):
                                    blink_counters[match_id]['blinked'] = False 
                                color = (0, 255, 0)
                                status_text = f"{name}: Verified"
                        else:
                            color = (255, 255, 0) # Cyan (Confirming...)
                            status_text = f"Confirming {name}..."
                    else:
                        color = (0, 0, 255)
                        status_text = "Unknown Person"
                        # Reset buffers for unknown
                        identity_buffer = {} 
                else:
                    color = (0, 0, 255)
                    status_text = "Unknown Person (No Registrations)"

                # Draw Results
                h, w, _ = img.shape
                min_x = int(min([l.x for l in face_landmarks]) * w)
                max_x = int(max([l.x for l in face_landmarks]) * w)
                min_y = int(min([l.y for l in face_landmarks]) * h)
                max_y = int(max([l.y for l in face_landmarks]) * h)
                
                cv2.rectangle(img, (min_x, min_y), (max_x, max_y), color, 2)
                cv2.putText(img, status_text, (min_x, min_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        cv2.imshow('MediaPipe Tasks Attendance', img)
        if cv2.waitKey(1) & 0xFF == ord('q'): break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    # In standalone mode, use Org 1 (Vidyalaya Main) or ask
    run_attendance(org_id=1)
