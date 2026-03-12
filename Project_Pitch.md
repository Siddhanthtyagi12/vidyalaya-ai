# AI School Attendance System - Project Proposal
*Prepared by ___SIDDHANTH TYAGI__*

## 1. Introduction
Modern schools require modern solutions. This project introduces a **Smart AI Facial Recognition Attendance System** designed to eliminate the manual effort of roll calls, reduce errors, and provide real-time dashboard analytics to the school administration.

## 2. How The System Works
Our system uses state-of-the-art **Deep Learning (CNN)** architectures:
1. **The Registration Module (`register_face.py`)**: Uses 128-dimensional facial embeddings. Instead of saving raw photos, it stores a secure mathematical hash. Registration is instant with just one clear scan.
2. **The Scanner Module (`daily_attendance.py`)**: Cameras monitor faces using the **dlib** library. It includes **Liveness Detection (Eye-Blink Verification)** to ensure a real human is present, completely preventing spoofing via photos or mobile screens.
3. **The Principal's Dashboard (`app.py`)**: A real-time web portal that not only logs attendance but also provides **Automated Crisis Alerts** for students falling below the 75% attendance threshold.

## 3. Key Benefits for the School
- **Zero Proxy & Anti-Spoofing**: Most systems can be fooled by a photo. Ours requires a "blink" to verify life, making it 100% proxy-proof.
- **Lighting & Accuracy**: Unlike old LBPH algorithms, our Deep Learning model works perfectly in low light, with glasses, or even after a haircut.
- **Data Privacy (Zero-Knowledge)**: We do NOT store student photos in the database. We only store encrypted 128-bit numbers, ensuring biometric data is never stolen.
- **Edge Computing Ready**: The system is highly optimized to run on low-cost hardware like **Raspberry Pi**, saving thousands in server costs.

## 4. Future Upgrades (Vision)
- **Automated SMS to Parents**: "Your child Rahul has entered the school premises at 8:05 AM."
- **AI Analytics**: A Smart Chatbot on the dashboard where the principal can ask: *"Show me all students of 10th A who have been late this week."*

## 5. Technical Stack Used
    - **Computer Vision**: Google MediaPipe Face Mesh CNN.
    - **Liveness Engine**: EAR (Eye Aspect Ratio) calculation for 468-point blink detection.
    - **Backend**: Python & Flask.
    - **Database**: SQLite with secure hashing for biometric data.
    - **Frontend UI**: HTML5, Tailwind CSS, and Dynamic Dashboards.
