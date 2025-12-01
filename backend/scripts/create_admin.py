#!/usr/bin/env python3
"""
Script to create an admin user or promote an existing user to admin.
Usage: python create_admin.py
"""

import sys
import os
from pathlib import Path
from getpass import getpass
from datetime import datetime, timezone

# Add the src directory to the python path
current_dir = Path(__file__).resolve().parent
src_dir = current_dir.parent / "src"
sys.path.insert(0, str(src_dir))

from homepot.app.db.database import SessionLocal
from homepot.app.models.UserRegisterModel import User
from homepot.app.auth_utils import hash_password

def create_admin():
    print("=== Create Admin User ===")
    email = input("Email: ").strip()
    if not email:
        print("Email is required.")
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        
        if user:
            print(f"User {email} already exists.")
            if user.is_admin:
                print("User is already an admin.")
                return
            
            confirm = input(f"Promote existing user {email} to admin? (y/n): ").lower()
            if confirm == 'y':
                user.is_admin = True
                user.updated_at = datetime.now(timezone.utc)
                db.commit()
                print(f"Successfully promoted {email} to admin.")
            else:
                print("Operation cancelled.")
        else:
            print(f"User {email} not found. Creating new admin user.")
            username = input("Username: ").strip()
            password = getpass("Password: ")
            confirm_password = getpass("Confirm Password: ")
            
            if password != confirm_password:
                print("Passwords do not match.")
                return
            
            if not username:
                print("Username is required.")
                return
                
            # Check if username exists
            existing_username = db.query(User).filter(User.username == username).first()
            if existing_username:
                print(f"Username {username} is already taken.")
                return
            
            new_user = User(
                email=email,
                username=username,
                hashed_password=hash_password(password),
                is_admin=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            
            db.add(new_user)
            db.commit()
            print(f"Successfully created admin user {email}.")
            
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()
