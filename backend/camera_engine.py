import cv2
import numpy as np
import os
import pickle
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions, RunningMode
from multiprocessing import Process, Queue, Manager
import time
import sys
# Add root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import db_operations
from datetime import datetime

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
                log_message(f"[ERROR-CAM-{self.camera_id}] Could NOT open source: {self.source}.")
                return
            
            log_message(f"[CAM-{self.camera_id}] Source opened. Testing frame read...")
            ret, test_frame = cap.read()
            if not ret:
                log_message(f"[ERROR-CAM-{self.camera_id}] Opened, but could NOT read frame.")
                cap.release()
                return
            
            log_message(f"[CAM-{self.camera_id}] Success! Starting main loop with cv2.imshow...")

            identity_buffer = {} # {id: frame_count}
            STABILITY_FRAMES = 5
            
            while self.running:
                ret, frame = cap.read()
                if not ret: break
                
                # Visualization (Show what the camera sees)
                display_frame = frame.copy()
                
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                result = landmarker.detect(mp_image)
                
                if result.face_landmarks:
                    for face_landmarks in result.face_landmarks:
                        # landmark point
                        h, w, c = frame.shape
                        p1 = face_landmarks[0]
                        cx, cy = int(p1.x * w), int(p1.y * h)
                        
                        # Recognition Logic
                        sig = []
                        for l in face_landmarks:
                            sig.extend([l.x, l.y, l.z])
                        sig = np.array(sig)
                        sig = sig - np.mean(sig)
                        norm = np.linalg.norm(sig)
                        if norm > 0: sig = sig / norm
                        
                        user_name = "Unknown"
                        if known_signatures:
                            distances = [np.linalg.norm(sig - ks) for ks in known_signatures]
                            best_idx = np.argmin(distances)
                            
                            if distances[best_idx] < self.threshold:
                                user_id = known_ids[best_idx]
                                user_name = names_dict.get(user_id, "Unknown")
                                identity_buffer[user_id] = identity_buffer.get(user_id, 0) + 1
                                
                                if identity_buffer[user_id] >= STABILITY_FRAMES:
                                    today = datetime.now().strftime('%Y-%m-%d')
                                    cache_key = f"{user_id}_{today}"
                                    if cache_key not in self.shared_cache:
                                        self.attendance_queue.put({
                                            'user_id': user_id, 
                                            'org_id': self.org_id,
                                            'name': user_name,
                                            'camera_id': self.camera_id
                                        })
                                        self.shared_cache[cache_key] = time.time()
                            else:
                                # Reset buffers if no match
                                pass
                        
                        # Draw on frame
                        cv2.putText(display_frame, user_name, (cx, cy-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                        cv2.circle(display_frame, (cx, cy), 3, (0, 255, 0), -1)

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
            db_operations.mark_attendance_db(
                data['user_id'], 
                data['org_id'], 
                datetime.now().strftime('%Y-%m-%d'),
                datetime.now().strftime('%H:%M:%S')
            )
            print(f"[ENGINE] Marked Attendance for {data['name']} from Camera {data['camera_id']}")

if __name__ == "__main__":
    # Test stub
    engine = EngineOrchestrator()
    # In production, app.py will call start_camera for each row in Cameras table
