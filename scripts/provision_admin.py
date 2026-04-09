#!/usr/bin/env python3
"""
Create the first local admin account for a customer installation.
"""
from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.core.security import get_password_hash  # noqa: E402
from app.db.base import SessionLocal  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402


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
        existing_username = db.query(User).filter(User.username == username).first()
        if existing_username:
            print(f"User '{username}' already exists.")
            return 1

        existing_email = db.query(User).filter(User.email == email.lower()).first()
        if existing_email:
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
