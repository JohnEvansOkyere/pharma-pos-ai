#!/usr/bin/env python3
"""
Create the first local admin account for a customer installation.

Run inside the backend container:
    docker exec -it pharma-pos-backend python scripts/provision_admin.py
"""
from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import get_password_hash
from app.db.base import SessionLocal
from app.models.user import User, UserRole


def _read_value(prompt: str, env_name: str, *, secret: bool = False) -> str:
    env_value = os.getenv(env_name, "").strip()
    if env_value:
        return env_value
    if secret:
        return getpass.getpass(prompt).strip()
    return input(prompt).strip()


def main() -> int:
    username = _read_value("Admin username: ", "PHARMA_ADMIN_USERNAME")
    email = _read_value("Admin email: ", "PHARMA_ADMIN_EMAIL")
    full_name = _read_value("Admin full name: ", "PHARMA_ADMIN_FULL_NAME")
    password = _read_value("Admin password: ", "PHARMA_ADMIN_PASSWORD", secret=True)

    if not username or not email or not full_name or not password:
        print("All admin fields are required.")
        return 1

    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == username).first():
            print(f"User '{username}' already exists.")
            return 1
        if db.query(User).filter(User.email == email.lower()).first():
            print(f"Email '{email}' is already in use.")
            return 1

        user = User(
            username=username,
            email=email.lower(),
            full_name=full_name,
            hashed_password=get_password_hash(password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(user)
        db.commit()
        print(f"Admin account '{username}' created successfully.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
