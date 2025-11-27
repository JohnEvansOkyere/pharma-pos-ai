#!/usr/bin/env python3
"""
Script to generate notifications for expiring products and low stock.
This manually triggers the notification checks to populate the notifications.
"""
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.db.base import SessionLocal
from app.services.notification_service import NotificationService


def main():
    """Generate notifications for current issues."""
    db = SessionLocal()
    try:
        print("Checking for expiring products...")
        NotificationService.check_expiring_products(db)
        print("Expiry check complete!")

        print("\nChecking for near expiry products (critical)...")
        NotificationService.check_near_expiry(db)
        print("Near expiry check complete!")

        print("\nChecking for low stock products...")
        NotificationService.check_low_stock(db)
        print("Low stock check complete!")

        print("\nChecking for out of stock products...")
        NotificationService.check_out_of_stock(db)
        print("Out of stock check complete!")

        print("\nChecking for overstocked products...")
        NotificationService.check_overstock(db)
        print("Overstock check complete!")

        print("\nChecking for dead stock products...")
        NotificationService.check_dead_stock(db)
        print("Dead stock check complete!")

        print("\nAll notifications generated successfully!")

    except Exception as e:
        print(f"Error generating notifications: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
