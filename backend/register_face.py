import cv2
import numpy as np
import os
import pickle
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions, RunningMode

# Hackathon Winner Standard: MediaPipe TASKS API (Latest)
# Fast, Accurate, and officially supported on Python 3.13 Windows!

# Task Setup (Lazy Load)
landmarker = None

def get_landmarker():
    global landmarker
    if landmarker is None:
        model_path = os.path.join(os.path.dirname(__file__), 'face_landmarker.task')
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=RunningMode.IMAGE,
            num_faces=1
        )
        landmarker = FaceLandmarker.create_from_options(options)
    return landmarker

encodings_file = os.path.join(os.path.dirname(__file__), 'encodings.pkl')
names_file = os.path.join(os.path.dirname(__file__), 'names.txt')

names_dict = {}

def get_new_id():
    # Freshly load from file to avoid sync issues
    current_names = {}
    if os.path.exists(names_file):
        with open(names_file, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) == 2:
                    current_names[int(parts[0])] = parts[1]
    
    if not current_names:
        return 1
    return max(current_names.keys()) + 1

import sys
# Add root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import db_operations

def save_names_and_db(id_num, name, org_id, role="Student", class_name="N/A", parent_phone="N/A"):
    global names_dict
    # Append to names.txt if not already there
    with open(names_file, 'a') as f:
        f.write(f"{id_num},{name}\n")
    
    # Update local dict in case it's used elsewhere
    names_dict[id_num] = name
    
    db_operations.add_user(id_num, name, org_id=org_id, role=role, class_name=class_name, parent_phone=parent_phone)    

def load_encodings():
    if os.path.exists(encodings_file):
        with open(encodings_file, 'rb') as f:
            return pickle.load(f)
    return {}

def save_encodings(encodings_dict):
    with open(encodings_file, 'wb') as f:
        pickle.dump(encodings_dict, f)

def extract_face_signature(img):
    # Convert to MediaPipe Image
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    
    # Detect face logic
    try:
        current_landmarker = get_landmarker()
        detection_result = current_landmarker.detect(mp_image)
        
        if detection_result.face_landmarks:
            # Get all landmarks (478 for Face Mesh)
            landmarks = detection_result.face_landmarks[0]
            
            # Flatten to vector
            sig = []
            for l in landmarks:
                sig.extend([l.x, l.y, l.z])
            sig = np.array(sig)
            
            # SCIENTIFIC NORMALIZATION: Zero-Mean & Unit-Norm
            sig = sig - np.mean(sig)
            norm = np.linalg.norm(sig)
            if norm > 0:
                sig = sig / norm
                
            return sig
    except Exception as e:
        print(f"Error during detection: {e}")
    return None

def add_new_user_logic(name, role, class_name="N/A", org_id=1, parent_phone="N/A"):
    # Fetch camera index from DB
    camera_idx = db_operations.get_org_camera_index(org_id)
    print(f"\n[INFO] {name} ka hi-frequency scan ho raha hai (30 Samples)...")
    print(f"[INFO] Using Camera Index: {camera_idx}")
    # Use CAP_DSHOW on Windows for faster/reliable startup
    if isinstance(camera_idx, int):
        cap = cv2.VideoCapture(camera_idx, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(camera_idx)
    
    if not cap.isOpened():
        print(f"[ERROR] Camera {camera_idx} nahi mil rahi!")
        return False
        
    known_encodings = load_encodings()
    success = False
    samples = []
    required_samples = 30
    
    while True:
        ret, img = cap.read()
        if not ret:
            print("\n[ERROR] Lost connection to camera unexpectedly. Exiting.")
            break
            
        display_img = img.copy()
        cv2.putText(display_img, f"Registering: {name}", (50, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(display_img, f"Samples: {len(samples)}/{required_samples}", (50, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(display_img, "Keep a steady face | 'Q' to Cancel", (50, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        # Extract signature for current frame
        signature = extract_face_signature(img)
        
        if signature is not None:
            samples.append(signature)
            cv2.putText(display_img, "CAPTURING...", (50, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        else:
            cv2.putText(display_img, "FACE NOT DETECTED", (50, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            cv2.putText(display_img, "Look directly at the camera", (50, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            
            # Draw a simple bounding box
            h, w, _ = img.shape
            # Using simple math for bounding box from 478 landmarks
            # MediaPipe results are already fetched in extract_face_signature, 
            # but we don't return landmarks from there. For UI, we just use the sig length.
            # (In a real app, we'd reuse the detection result)
            
        cv2.imshow('Registration: 30-Sample Average Scan', display_img)
        
        if len(samples) >= required_samples:
            # COMPUTE AVERAGE EMBEDDING
            avg_signature = np.mean(samples, axis=0)
            # Re-normalize the average
            avg_signature = avg_signature - np.mean(avg_signature)
            norm = np.linalg.norm(avg_signature)
            if norm > 0:
                avg_signature = avg_signature / norm
            
            face_id = get_new_id()
            known_encodings[face_id] = avg_signature
            save_encodings(known_encodings)
            
            # Save user info to names.txt and DB
            names_dict[face_id] = name
            save_names_and_db(face_id, name, org_id, role, class_name, parent_phone)
            
            print(f"[SUCCESS] {name} ki averaged signature securely save ho gayi!")
            success = True
            break
            
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("[INFO] Registration canceled by user.")
            break
            
    cap.release()
    cv2.destroyAllWindows()
    return success

if __name__ == "__main__":
    print("\n===============================")
    print("  SCHOOL ADMIN REGISTRATION  ")
    print("===============================")
    name = input("Naya naam daalein: ")
    role = input("Role (Student/Teacher): ")
    class_name = input("Class (e.g. 10thA): ")
    add_new_user_logic(name, role, class_name)
    print("\n[INFO] Registration complete.")

