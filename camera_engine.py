import cv2
import numpy as np
import os
import pickle
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions, RunningMode
from multiprocessing import Process, Queue, Event, Manager
import time
import sys
from datetime import datetime
import json
import logging

def calculate_ear(landmarks, eye_indices):
    pts = [np.array([landmarks[i].x, landmarks[i].y]) for i in eye_indices]
    A = np.linalg.norm(pts[1] - pts[5])
    B = np.linalg.norm(pts[2] - pts[4])
    C = np.linalg.norm(pts[0] - pts[3])
    ear = (A + B) / (2.0 * C)
    return ear

# System configuration limits
MAX_CAMERAS = 4

# Add root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import db_operations

# Global config (Absolute paths relative to script location)
ENCODINGS_FILE = os.path.join(os.path.dirname(__file__), 'encodings.pkl')
NAMES_FILE = os.path.join(os.path.dirname(__file__), 'names.txt')
LOG_FILE = os.path.join(os.path.dirname(__file__), 'camera_engine.log')

def log_message(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    full_msg = f"[{timestamp}] {msg}\n"
    with open(LOG_FILE, 'a') as f:
        f.write(full_msg)
    print(msg, flush=True)

class CameraWorker(Process):
    def __init__(self, org_id, camera_id, source, threshold, attendance_queue, shared_cache):
        super(CameraWorker, self).__init__()
        self.org_id = org_id
        self.camera_id = camera_id
        try:
            self.source = int(source)
        except (ValueError, TypeError):
            self.source = source
        self.threshold = threshold
        self.attendance_queue = attendance_queue
        self.shared_cache = shared_cache # {user_id: last_marked_time}
        self.running = True

    def load_metadata(self):
        names_dict = {}
        if os.path.exists(NAMES_FILE):
            with open(NAMES_FILE, 'r') as f:
                for line in f:
                    parts = line.strip().split(',')
                    if len(parts) == 2:
                        names_dict[int(parts[0])] = parts[1]
        
        known_encodings_dict = {}
        if os.path.exists(ENCODINGS_FILE):
            with open(ENCODINGS_FILE, 'rb') as f:
                known_encodings_dict = pickle.load(f)
        
        return names_dict, known_encodings_dict

    def run(self):
        log_message(f"[CAM-{self.camera_id}] Starting process for source: {self.source}")
        try:
            # Initialize MediaPipe in this process
            model_path = os.path.join(os.path.dirname(__file__), 'face_landmarker.task')
            base_options = python.BaseOptions(model_asset_path=model_path)
            options = FaceLandmarkerOptions(
                base_options=base_options,
                running_mode=RunningMode.IMAGE,
                num_faces=5
            )
            landmarker = FaceLandmarker.create_from_options(options)
            
            names_dict, known_encodings_dict = self.load_metadata()
            known_ids = list(known_encodings_dict.keys())
            known_signatures = list(known_encodings_dict.values())
            
            log_message(f"[CAM-{self.camera_id}] MediaPipe and Metadata loaded. Attempting to open VideoCapture with CAP_DSHOW...")
            cap = cv2.VideoCapture(self.source, cv2.CAP_DSHOW)
            if not cap.isOpened():
                log_message(f"[INFO-CAM-{self.camera_id}] CAP_DSHOW failed. Retrying with default backend...")
                cap = cv2.VideoCapture(self.source)
                
            if not cap.isOpened():
                log_message(f"[ERROR-CAM-{self.camera_id}] Could NOT open source: {self.source}. (Check if index is correct or camera is in use)")
                return
            
            log_message(f"[CAM-{self.camera_id}] Source opened. Testing frame read...")
            ret, test_frame = cap.read()
            if not ret:
                log_message(f"[ERROR-CAM-{self.camera_id}] Opened, but could NOT read frame. (Source might be empty or restricted)")
                cap.release()
                return
            
            log_message(f"[CAM-{self.camera_id}] Success! Starting main loop with cv2.imshow...")

            identity_buffer = {} # {id: frame_count}
            verification_feedback = {} # {id: timestamp}
            blink_counters = {} # {id: {'count': 0, 'blinked': False}}
            STABILITY_FRAMES = 5
            
            LEFT_EYE = [33, 160, 158, 133, 153, 144]
            RIGHT_EYE = [362, 385, 387, 263, 373, 380]
            EAR_THRESHOLD = 0.18
            
            while self.running:
                ret, frame = cap.read()
                if not ret: break
                
                # Visualization (Show what the camera sees)
                display_frame = frame.copy()
                
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                result = landmarker.detect(mp_image)
                
                if result.face_landmarks:
                    for face_landmarks in result.face_landmarks:
                        # Get full face bounds
                        h, w, c = frame.shape
                        min_x = int(min([l.x for l in face_landmarks]) * w)
                        max_x = int(max([l.x for l in face_landmarks]) * w)
                        min_y = int(min([l.y for l in face_landmarks]) * h)
                        max_y = int(max([l.y for l in face_landmarks]) * h)
                        
                        min_x, min_y = max(0, min_x), max(0, min_y)
                        max_x, max_y = min(w, max_x), min(h, max_y)
                        # Recognition Logic
                        sig = []
                        for l in face_landmarks:
                            sig.extend([l.x, l.y, l.z])
                        sig = np.array(sig)
                        sig = sig - np.mean(sig)
                        norm = np.linalg.norm(sig)
                        if norm > 0: sig = sig / norm
                        
                        user_id = None
                        user_name = "Unknown"
                        color = (0, 0, 255) # Default Red
                        display_text = "Scanning..."
                        if known_signatures:
                            distances = [np.linalg.norm(sig - ks) for ks in known_signatures]
                            best_idx = np.argmin(distances)
                            best_dist = distances[best_idx]
                            
                            # Stability Check: Only proceed if best match is significantly better than second best
                            sorted_dists = sorted(distances)
                            second_best_dist = sorted_dists[1] if len(sorted_dists) > 1 else 9.0
                            confidence_gap = second_best_dist - best_dist
                            
                            if best_dist < self.threshold and confidence_gap > 0.05:
                                user_id = known_ids[best_idx]
                                user_name = names_dict.get(user_id, "Unknown")
                                
                                # Increment buffer for this user, decay others to prevent "flickering" memory
                                identity_buffer[user_id] = min(identity_buffer.get(user_id, 0) + 1, STABILITY_FRAMES + 10)
                                for oid in list(identity_buffer.keys()):
                                    if oid != user_id:
                                        identity_buffer[oid] = max(0, identity_buffer[oid] - 1)
                                
                                if identity_buffer[user_id] >= STABILITY_FRAMES:
                                    color = (0, 165, 255) # Orange (Ready for blink)
                                    display_text = f"{user_name}: Please Blink"
                                    
                                    # Liveness: Blink Detection
                                    ear = (calculate_ear(face_landmarks, LEFT_EYE) + 
                                           calculate_ear(face_landmarks, RIGHT_EYE)) / 2.0
                                           
                                    if user_id not in blink_counters:
                                        blink_counters[user_id] = {'count': 0, 'blinked': False}
                                        
                                    if ear < EAR_THRESHOLD:
                                        blink_counters[user_id]['count'] += 1
                                    else:
                                        if blink_counters[user_id]['count'] >= 2:
                                            blink_counters[user_id]['blinked'] = True
                                        blink_counters[user_id]['count'] = 0
                                        
                                    if blink_counters[user_id]['blinked']:
                                        today = datetime.now().strftime('%Y-%m-%d')
                                        cache_key = f"{user_id}_{today}"
                                        
                                        if cache_key not in self.shared_cache:
                                            log_message(f"[CAM-{self.camera_id}] Queuing attendance for {user_name}")
                                            self.attendance_queue.put({
                                                'user_id': user_id, 
                                                'org_id': self.org_id,
                                                'name': user_name,
                                                'camera_id': self.camera_id
                                            })
                                            self.shared_cache[cache_key] = time.time()
                                            verification_feedback[user_id] = time.time()
                                            blink_counters[user_id]['blinked'] = False # reset
                                        
                                        color = (0, 255, 0)
                                        display_text = f"{user_name}: Verified"
                                else:
                                    color = (255, 255, 0)
                                    display_text = f"Confirming {user_name}..."
                            else:
                                color = (0, 0, 255)
                                display_text = "Unknown"
                                
                        # Draw on frame
                        if user_id in verification_feedback:
                            if time.time() - verification_feedback[user_id] < 3.0:
                                color = (0, 255, 0)
                                display_text = f"{user_name}: Verified"
                            else:
                                del verification_feedback[user_id]
                        
                        cv2.rectangle(display_frame, (min_x, min_y), (max_x, max_y), color, 2)
                        text_y = min_y - 10 if min_y - 10 > 10 else min_y + 20
                        cv2.putText(display_frame, display_text, (min_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                cv2.imshow(f"Attendance Feed - Camera {self.camera_id}", display_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            
        except Exception as e:
            log_message(f"[CRITICAL-ERROR-CAM-{self.camera_id}] {str(e)}")
        finally:
            if 'cap' in locals() and cap.isOpened():
                cap.release()
            cv2.destroyAllWindows()
            log_message(f"[CAM-{self.camera_id}] Process terminated and resources released.")

class EngineOrchestrator:
    def __init__(self):
        self.manager = Manager()
        self.shared_cache = self.manager.dict()
        self.attendance_queue = Queue()
        self.active_processes = {} # {camera_id: Process}

    def start_camera(self, org_id, camera_id, source, threshold):
        camera_id = str(camera_id)
        if camera_id in self.active_processes:
            self.stop_camera(camera_id)
            
        p = CameraWorker(org_id, camera_id, source, threshold, self.attendance_queue, self.shared_cache)
        p.start()
        self.active_processes[camera_id] = p

    def stop_camera(self, camera_id):
        camera_id = str(camera_id)
        if camera_id in self.active_processes:
            self.active_processes[camera_id].terminate()
            self.active_processes[camera_id].join() # Wait for process to fully terminate
            del self.active_processes[camera_id]

    def process_attendance_queue(self):
        """This should run in the main thread/process to update DB."""
        while not self.attendance_queue.empty():
            data = self.attendance_queue.get()
            try:
                db_operations.mark_attendance_db(
                    data['user_id'], 
                    data['org_id'], 
                    datetime.now().strftime('%Y-%m-%d'),
                    datetime.now().strftime('%H:%M:%S')
                )
                log_message(f"[ENGINE] SUCCESS: Marked Attendance for {data['name']} from Camera {data['camera_id']}")
            except Exception as e:
                log_message(f"[ENGINE] ERROR marking attendance for {data.get('name')}: {e}")

if __name__ == "__main__":
    # Test stub
    engine = EngineOrchestrator()
    # In production, app.py will call start_camera for each row in Cameras table
