import os
import pickle
import sys
# Add root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import db_operations

def delete_user_workflow():
    # Use absolute paths relative to backend folder where data resides
    names_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend', 'names.txt')
    encodings_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend', 'encodings.pkl')
    
    if not os.path.exists(names_file):
        print(f"[ERROR] names.txt nahi mili! (Path: {names_file})")
        return

    # 1. Load aur display users
    users = {}
    with open(names_file, 'r') as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) == 2:
                users[parts[0]] = parts[1]
    
    if not users:
        print("[INFO] Koi registered user nahi mila.")
        return

    print("\n--- Registered Users ---")
    for uid, name in users.items():
        print(f"ID: {uid} | Name: {name}")
    print("------------------------")

    # 2. Input ID to delete
    try:
        del_id = input("\nDelete karne ke liye ID daalein (Ya cancel karne ke liye 'c' dabayein): ").strip()
        if del_id.lower() == 'c':
            print("Operation cancelled.")
            return
        
        if del_id not in users:
            print(f"[ERROR] ID {del_id} nahi mila!")
            return
        
        users_copy = users[del_id]
        confirm = input(f"Kya aap pakka '{users_copy}' (ID: {del_id}) ko delete karna chahte hain? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Operation cancelled.")
            return

        # 3. Remove from names.txt
        print(f"[INFO] names.txt se hataya ja raha hai...")
        del users[del_id]
        with open(names_file, 'w') as f:
            for uid, name in users.items():
                f.write(f"{uid},{name}\n")

        # 4. Remove from encodings.pkl
        if os.path.exists(encodings_file):
            print(f"[INFO] encodings.pkl se data hataya ja raha hai...")
            with open(encodings_file, 'rb') as f:
                encodings = pickle.load(f)
            
            if int(del_id) in encodings:
                del encodings[int(del_id)]
                with open(encodings_file, 'wb') as f:
                    pickle.dump(encodings, f)
                print(f"[INFO] Face signature delete ho gayi.")

        # 5. Remove from Database
        print(f"[INFO] Database se record hataya ja raha hai...")
        try:
            # Note: We need org_id here. Defaulting to 1 for CLI tool.
            db_operations.delete_user(int(del_id), org_id=1) 
        except Exception as e:
            print(f"[WARNING] DB deletion fail hua: {e}")

        print(f"\n[SUCCESS] '{users_copy}' poori tarah se delete ho chuka hai!")

    except Exception as e:
        print(f"[ERROR] Kuch galat hua: {e}")

        print(f"\n[SUCCESS] '{users_copy}' poori tarah se delete ho chuka hai!")

    except Exception as e:
        print(f"[ERROR] Kuch galat hua: {e}")

if __name__ == "__main__":
    delete_user_workflow()
