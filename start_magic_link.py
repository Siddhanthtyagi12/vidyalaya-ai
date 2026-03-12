import time
import os
from pyngrok import ngrok

def start_tunnel():
    print("[INFO] Setting up your Magic Link (Ngrok)...")
    try:
        # Open a HTTP tunnel on port 8000
        public_url = ngrok.connect(8000).public_url
        print(f"\n[SUCCESS] Your Magic Link is: {public_url}")
        print("[INFO] Keep this window open while using the app.")
        print("[INFO] Updating mobile app config...")
        
        # Update Config.js
        config_path = r"d:\sidprojects\mobile_app\src\constants\Config.js"
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                lines = f.readlines()
            
            with open(config_path, 'w') as f:
                for line in lines:
                    if 'API_BASE_URL' in line:
                        f.write(f"export const API_BASE_URL = '{public_url}';\n")
                    else:
                        f.write(line)
            print("[INFO] Config.js updated successfully!")
            
        print("\n[READY] Now start your API Server using START_API_MOBILE.bat")
        
        while True:
            time.sleep(1)
            
    except Exception as e:
        print(f"[ERROR] Could not start Magic Link: {e}")
        print("[TIP] You might need to sign up at ngrok.com and run 'ngrok config add-authtoken <your_token>'")

if __name__ == "__main__":
    start_tunnel()
