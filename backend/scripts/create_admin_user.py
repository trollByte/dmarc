#!/usr/bin/env python3
"""
Bootstrap script to create the first admin user.

Usage:
    python scripts/create_admin_user.py

Or via Docker:
    docker compose exec backend python scripts/create_admin_user.py

Interactive prompts will ask for:
- Username
- Email
- Password (hidden input)
"""

import sys
import os
import getpass

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import User, UserRole
from app.services.auth_service import AuthService, PasswordValidationError


def create_admin_user():
    """Interactive script to create admin user"""
    print("=" * 60)
    print("  DMARC Dashboard - Create Admin User")
    print("=" * 60)
    print()

    db = SessionLocal()

    try:
        # Check if any admin users exist
        existing_admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
        if existing_admin:
            print("⚠️  Warning: Admin user(s) already exist!")
            print(f"   Existing admin: {existing_admin.username}")
            print()
            response = input("Do you want to create another admin user? (yes/no): ").strip().lower()
            if response not in ['yes', 'y']:
                print("❌ Aborted.")
                return

        print("Creating new admin user...")
        print()

        # Prompt for username
        while True:
            username = input("Username: ").strip()
            if not username:
                print("❌ Username cannot be empty")
                continue
            if len(username) < 3:
                print("❌ Username must be at least 3 characters")
                continue

            # Check if username exists
            if db.query(User).filter(User.username == username).first():
                print(f"❌ Username '{username}' already exists")
                continue

            break

        # Prompt for email
        while True:
            email = input("Email: ").strip()
            if not email:
                print("❌ Email cannot be empty")
                continue
            if '@' not in email:
                print("❌ Invalid email address")
                continue

            # Check if email exists
            if db.query(User).filter(User.email == email).first():
                print(f"❌ Email '{email}' already exists")
                continue

            break

        # Prompt for password
        while True:
            password = getpass.getpass("Password: ")
            if not password:
                print("❌ Password cannot be empty")
                continue

            # Validate password policy
            try:
                AuthService.validate_password_policy(password)
            except PasswordValidationError as e:
                print(f"❌ Password validation failed: {e}")
                print()
                print("Password requirements:")
                print("  - Minimum 12 characters")
                print("  - At least one uppercase letter")
                print("  - At least one lowercase letter")
                print("  - At least one digit")
                print("  - At least one special character (!@#$%^&*(),.?\":{}|<>)")
                print()
                continue

            # Confirm password
            password_confirm = getpass.getpass("Confirm password: ")
            if password != password_confirm:
                print("❌ Passwords do not match")
                continue

            break

        print()
        print("Summary:")
        print(f"  Username: {username}")
        print(f"  Email:    {email}")
        print(f"  Role:     admin")
        print()

        response = input("Create this admin user? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("❌ Aborted.")
            return

        # Hash password
        hashed_password = AuthService.hash_password(password)

        # Create user
        admin_user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            role=UserRole.ADMIN,
            is_active=True,
            is_locked=False,
            failed_login_attempts=0
        )

        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

        print()
        print("=" * 60)
        print("✅ Admin user created successfully!")
        print("=" * 60)
        print()
        print(f"User ID:  {admin_user.id}")
        print(f"Username: {admin_user.username}")
        print(f"Email:    {admin_user.email}")
        print(f"Role:     {admin_user.role.value if hasattr(admin_user.role, 'value') else admin_user.role}")
        print()
        print("You can now login with these credentials:")
        print(f"  POST /auth/login")
        print(f"  {{ \"username\": \"{username}\", \"password\": \"<your-password>\" }}")
        print()
        print("Next steps:")
        print("  1. Login to get JWT tokens")
        print("  2. Use access token in Authorization header: Bearer <token>")
        print("  3. Create additional users via POST /users (admin only)")
        print()

    except KeyboardInterrupt:
        print("\n\n❌ Aborted by user.")
        db.rollback()
    except Exception as e:
        print(f"\n❌ Error creating admin user: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_admin_user()
