import sys
import os

# Simulate Render environment (roughly)
sys.path.append(os.getcwd())

try:
    from backend.cloud_server import app
    print("SUCCESS: backend.cloud_server.app imported successfully!")
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
