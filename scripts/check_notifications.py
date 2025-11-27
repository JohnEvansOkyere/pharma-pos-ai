#!/usr/bin/env python3
"""
Script to check generated notifications.
"""
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.db.base import SessionLocal
from app.models.notification import Notification

def main():
    """Check generated notifications."""
    db = SessionLocal()
    try:
        notifications = db.query(Notification).order_by(Notification.created_at.desc()).all()

        print(f"\n{'='*60}")
        print(f"Total notifications: {len(notifications)}")
        print(f"{'='*60}\n")

        # Group by type
        by_type = {}
        for n in notifications:
            type_name = n.type.value
            if type_name not in by_type:
                by_type[type_name] = 0
            by_type[type_name] += 1

        print("Notifications by type:")
        for type_name, count in sorted(by_type.items()):
            print(f"  {type_name:20s}: {count}")

        print(f"\n{'='*60}")
        print("Recent notifications:")
        print(f"{'='*60}\n")

        for n in notifications[:10]:
            priority_emoji = {
                'LOW': '🟢',
                'MEDIUM': '🟡',
                'HIGH': '🟠',
                'CRITICAL': '🔴'
            }.get(n.priority.value, '⚪')

            print(f"{priority_emoji} [{n.type.value.upper():15s}] {n.title}")
            print(f"   {n.message}")
            print(f"   {n.created_at}\n")

    finally:
        db.close()

if __name__ == "__main__":
    main()
