import pyrebase
import time

firebase_config = {
    "apiKey": "AIzaSyDWFMffpD2q3N9EEbiZxVGgMfXuGTp4gEc",
    "authDomain": "health-monitor-c806e.firebaseapp.com",
    "databaseURL": "https://health-monitor-c806e-default-rtdb.firebaseio.com",
    "projectId": "health-monitor-c806e",
    "storageBucket": "health-monitor-c806e.appspot.com",
    "messagingSenderId": "853926503929",
    "appId": "1:853926503929:web:20a9caefdb98aa5dc38928",
    "measurementId": "G-PE1T81110S"
}

firebase = pyrebase.initialize_app(firebase_config)
db = firebase.database()
auth = firebase.auth()

DEVICE_ID = "raspi4-001"

def safe_push(path, data):
    try:
        db.child("devices").child(DEVICE_ID).child(path).push(data)
        print(f"✅ Uploaded to {path}")
    except Exception as e:
        print(f"❌ Firebase upload failed for {path}:", e)

# ===== Fingerprint =====
def push_fingerprint(event, finger_id, result, user_email=None):
    data = {"event": event, "finger_id": int(finger_id), "result": bool(result), "timestamp": time.time()}
    try:
        if user_email:
            key = user_email.replace(".", "_")
            db.child("devices").child(DEVICE_ID).child("fingerprints").child(key).set(data)
        else:
            safe_push("fingerprints", data)
        print(f"✅ Fingerprint data stored for {user_email}")
    except Exception as e:
        print(f"❌ Firebase upload failed for fingerprint:", e)

def delete_fingerprint_from_db(user_email):
    if not user_email: return
    try:
        key = user_email.replace(".", "_")
        db.child("devices").child(DEVICE_ID).child("fingerprints").child(key).remove()
        print(f"✅ Fingerprint data removed for {user_email}")
    except Exception as e:
        print(f"❌ Failed to remove fingerprint data for {user_email}: {e}")

# ===== ECG =====
def push_ecg_batch(samples_array, fs=100, user_email=None):
    data = {"fs": fs, "samples": list(map(int, samples_array)), "timestamp": time.time()}
    try:
        if user_email:
            key = user_email.replace(".", "_")
            db.child("devices").child(DEVICE_ID).child("ecg").child(key).set(data)
        else:
            db.child("devices").child(DEVICE_ID).child("ecg").push(data)
        print(f"✅ ECG data stored for {user_email}")
    except Exception as e:
        print(f"❌ Firebase upload failed for ECG:", e)

# ===== Pulse =====
def push_pulse(bpm, status, user_email=None):
    data = {"bpm": int(bpm), "status": status, "timestamp": time.time()}
    try:
        if user_email:
            key = user_email.replace(".", "_")
            db.child("devices").child(DEVICE_ID).child("pulses").child(key).set(data)
        else:
            db.child("devices").child(DEVICE_ID).child("pulses").push(data)
        print(f"✅ Pulse data stored for {user_email}")
    except Exception as e:
        print(f"❌ Firebase upload failed for Pulse:", e)

# ===== Firebase Auth =====
def signup_user(email, password):
    try:
        user = auth.create_user_with_email_and_password(email, password)
        print("✅ User signed up:", email)
        return user
    except Exception as e:
        print("❌ Signup failed:", e)
        return None

def login_user(email, password):
    try:
        user = auth.sign_in_with_email_and_password(email, password)
        print("✅ User logged in:", email)
        return user
    except Exception as e:
        print("❌ Login failed:", e)
        return None
