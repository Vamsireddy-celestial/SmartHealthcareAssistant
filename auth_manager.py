import os
import json
import hashlib
import secrets
from datetime import datetime

# ── User Store (JSON file based) ─────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, 'data', 'admin_users.json')

def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{hashed}"

def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, hashed = stored.split(':')
        return hashlib.sha256((salt + password).encode()).hexdigest() == hashed
    except Exception:
        return False

def _load_users() -> dict:
    if not os.path.exists(USERS_FILE):
        _init_default_users()
    with open(USERS_FILE, 'r') as f:
        return json.load(f)

def _save_users(users: dict):
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def _init_default_users():
    """Create default superadmin on first run."""
    users = {
        "admin": {
            "username":   "admin",
            "password":   _hash_password("Health@Admin2026"),
            "role":       "superadmin",
            "name":       "Super Admin",
            "email":      "admin@smarthealthcare.in",
            "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "created_by": "system",
            "active":     True,
            "last_login": None,
        }
    }
    _save_users(users)
    print("✅ Default admin users created.")

# ── RBAC Permissions ─────────────────────────────────────────────────────────
ROLE_PERMISSIONS = {
    "superadmin": [
        "view_dashboard", "view_consultations", "manage_camps",
        "manage_users", "view_analytics", "download_reports", "view_security"
    ],
    "admin": [
        "view_dashboard", "view_consultations", "manage_camps",
        "view_analytics", "download_reports"
    ],
    "doctor": [
        "view_dashboard", "view_consultations"
    ],
    "viewer": [
        "view_dashboard"
    ],
}

ROLE_LABELS = {
    "superadmin": "🔴 Super Admin",
    "admin":      "🟠 Admin",
    "doctor":     "🟢 Doctor",
    "viewer":     "🔵 Viewer",
}

def has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, [])

# ── Auth Functions ────────────────────────────────────────────────────────────
def login_user(username: str, password: str):
    """Returns user dict if valid, None otherwise."""
    users = _load_users()
    user  = users.get(username.strip().lower())
    if not user:
        return None
    if not user.get('active', True):
        return None
    if not _verify_password(password, user['password']):
        return None
    # Update last login
    user['last_login'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    users[username] = user
    _save_users(users)
    return user

def get_all_users() -> list:
    users = _load_users()
    return [
        {k: v for k, v in u.items() if k != 'password'}
        for u in users.values()
    ]

def get_user(username: str) -> dict:
    users = _load_users()
    u = users.get(username)
    if u:
        return {k: v for k, v in u.items() if k != 'password'}
    return None

def add_user(username: str, password: str, name: str,
             email: str, role: str, created_by: str) -> tuple:
    """Returns (success, message)."""
    if role not in ROLE_PERMISSIONS:
        return False, f"Invalid role. Choose from: {', '.join(ROLE_PERMISSIONS.keys())}"
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    if not username or not name:
        return False, "Username and name are required."

    username = username.strip().lower()
    users    = _load_users()

    if username in users:
        return False, f"Username '{username}' already exists."

    users[username] = {
        "username":   username,
        "password":   _hash_password(password),
        "role":       role,
        "name":       name,
        "email":      email,
        "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "created_by": created_by,
        "active":     True,
        "last_login": None,
    }
    _save_users(users)
    return True, f"User '{username}' created successfully."

def update_user(username: str, data: dict, updated_by: str) -> tuple:
    """Update name, email, role, or password."""
    users = _load_users()
    if username not in users:
        return False, "User not found."

    user = users[username]

    # Prevent demoting last superadmin
    if user['role'] == 'superadmin' and data.get('role') != 'superadmin':
        superadmins = [u for u in users.values() if u['role'] == 'superadmin' and u['active']]
        if len(superadmins) <= 1:
            return False, "Cannot change role — must have at least one superadmin."

    if 'name'  in data: user['name']  = data['name']
    if 'email' in data: user['email'] = data['email']
    if 'role'  in data and data['role'] in ROLE_PERMISSIONS:
        user['role'] = data['role']
    if 'password' in data and data['password']:
        if len(data['password']) < 6:
            return False, "Password must be at least 6 characters."
        user['password'] = _hash_password(data['password'])

    user['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    user['updated_by'] = updated_by
    users[username]    = user
    _save_users(users)
    return True, "User updated successfully."

def toggle_user(username: str, toggled_by: str) -> tuple:
    users = _load_users()
    if username not in users:
        return False, "User not found."
    if username == toggled_by:
        return False, "You cannot deactivate your own account."

    user = users[username]
    if user['role'] == 'superadmin' and user['active']:
        superadmins = [u for u in users.values() if u['role'] == 'superadmin' and u['active']]
        if len(superadmins) <= 1:
            return False, "Cannot deactivate — must have at least one active superadmin."

    user['active'] = not user.get('active', True)
    users[username] = user
    _save_users(users)
    status = "activated" if user['active'] else "deactivated"
    return True, f"User '{username}' {status}."

def delete_user(username: str, deleted_by: str) -> tuple:
    users = _load_users()
    if username not in users:
        return False, "User not found."
    if username == deleted_by:
        return False, "You cannot delete your own account."
    if users[username]['role'] == 'superadmin':
        superadmins = [u for u in users.values() if u['role'] == 'superadmin' and u['active']]
        if len(superadmins) <= 1:
            return False, "Cannot delete — must have at least one superadmin."
    del users[username]
    _save_users(users)
    return True, f"User '{username}' deleted."


# ── Password Reset (OTP-based) ───────────────────────────────────────────────
import random
import time

# In-memory OTP store {username: {'otp': '123456', 'expires': timestamp}}
_otp_store = {}

def generate_reset_otp(username: str) -> tuple:
    """Generate a 6-digit OTP for password reset. Returns (success, otp_or_message)."""
    users = _load_users()
    user  = users.get(username.strip().lower())
    if not user:
        return False, "Username not found."
    if not user.get('active', True):
        return False, "This account is deactivated. Contact Super Admin."

    otp     = str(random.randint(100000, 999999))
    expires = time.time() + 600  # 10 minutes

    _otp_store[username] = {'otp': otp, 'expires': expires, 'email': user.get('email', '')}
    print(f"🔑 OTP for {username}: {otp}")  # In production, send via email
    return True, otp

def verify_otp_and_reset(username: str, otp: str, new_password: str) -> tuple:
    """Verify OTP and reset password. Returns (success, message)."""
    username = username.strip().lower()
    entry    = _otp_store.get(username)

    if not entry:
        return False, "No OTP found. Please request a new one."
    if time.time() > entry['expires']:
        _otp_store.pop(username, None)
        return False, "OTP expired. Please request a new one."
    if entry['otp'] != otp.strip():
        return False, "Invalid OTP. Please try again."
    if len(new_password) < 6:
        return False, "Password must be at least 6 characters."

    users = _load_users()
    if username not in users:
        return False, "User not found."

    users[username]['password']   = _hash_password(new_password)
    users[username]['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    _save_users(users)
    _otp_store.pop(username, None)
    return True, "Password reset successfully! Please login with your new password."

def change_password(username: str, old_password: str, new_password: str) -> tuple:
    """Change password after verifying old password."""
    users = _load_users()
    user  = users.get(username)
    if not user:
        return False, "User not found."
    if not _verify_password(old_password, user['password']):
        return False, "Current password is incorrect."
    if len(new_password) < 6:
        return False, "New password must be at least 6 characters."
    if old_password == new_password:
        return False, "New password must be different from current password."

    users[username]['password']   = _hash_password(new_password)
    users[username]['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    _save_users(users)
    return True, "Password changed successfully!"
