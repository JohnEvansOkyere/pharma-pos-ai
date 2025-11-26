"""
Seed script to populate database with sample data for testing.
Run this script after running migrations.
"""
import sys
import os
from datetime import datetime, date, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.app.db.base import SessionLocal
from backend.app.models.user import User, UserRole
from backend.app.models.category import Category
from backend.app.models.supplier import Supplier
from backend.app.models.product import Product, ProductBatch
from backend.app.core.security import get_password_hash


def seed_database():
    """Seed the database with sample data."""
    db = SessionLocal()

    try:
        print("🌱 Seeding database...")

        # Create users
        print("Creating users...")
        users_data = [
            {
                "username": "admin",
                "email": "admin@pharmapos.com",
                "full_name": "Admin User",
                "password": "admin123",
                "role": UserRole.ADMIN,
            },
            {
                "username": "manager",
                "email": "manager@pharmapos.com",
                "full_name": "Manager User",
                "password": "manager123",
                "role": UserRole.MANAGER,
            },
            {
                "username": "cashier",
                "email": "cashier@pharmapos.com",
                "full_name": "Cashier User",
                "password": "cashier123",
                "role": UserRole.CASHIER,
            },
        ]

        for user_data in users_data:
            existing_user = db.query(User).filter(User.username == user_data["username"]).first()
            if not existing_user:
                user = User(
                    username=user_data["username"],
                    email=user_data["email"],
                    full_name=user_data["full_name"],
                    hashed_password=get_password_hash(user_data["password"]),
                    role=user_data["role"],
                    is_active=True,
                )
                db.add(user)
        db.commit()
        print("✓ Users created")

        # Create categories
        print("Creating categories...")
        categories_data = [
            {"name": "Antibiotics", "description": "Antimicrobial medications"},
            {"name": "Pain Relief", "description": "Analgesics and pain management"},
            {"name": "Vitamins", "description": "Vitamin supplements"},
            {"name": "Cold & Flu", "description": "Cold and flu medications"},
            {"name": "Digestive Health", "description": "Digestive system medications"},
            {"name": "Skin Care", "description": "Dermatological products"},
            {"name": "First Aid", "description": "First aid supplies"},
        ]

        categories = {}
        for cat_data in categories_data:
            existing_cat = db.query(Category).filter(Category.name == cat_data["name"]).first()
            if not existing_cat:
                category = Category(**cat_data)
                db.add(category)
                db.flush()
                categories[cat_data["name"]] = category.id
            else:
                categories[cat_data["name"]] = existing_cat.id
        db.commit()
        print("✓ Categories created")

        # Create suppliers
        print("Creating suppliers...")
        suppliers_data = [
            {
                "name": "MedSupply Co.",
                "contact_person": "John Doe",
                "email": "john@medsupply.com",
                "phone": "+1234567890",
                "address": "123 Medical St, Healthcare City",
            },
            {
                "name": "PharmaDirect Ltd.",
                "contact_person": "Jane Smith",
                "email": "jane@pharmadirect.com",
                "phone": "+1234567891",
                "address": "456 Pharmacy Ave, Medicine Town",
            },
            {
                "name": "HealthPlus Distributors",
                "contact_person": "Bob Johnson",
                "email": "bob@healthplus.com",
                "phone": "+1234567892",
                "address": "789 Wellness Blvd, Cure City",
            },
        ]

        suppliers = {}
        for sup_data in suppliers_data:
            existing_sup = db.query(Supplier).filter(Supplier.name == sup_data["name"]).first()
            if not existing_sup:
                supplier = Supplier(**sup_data)
                db.add(supplier)
                db.flush()
                suppliers[sup_data["name"]] = supplier.id
            else:
                suppliers[sup_data["name"]] = existing_sup.id
        db.commit()
        print("✓ Suppliers created")

        # Create products
        print("Creating products...")
        products_data = [
            {
                "name": "Amoxicillin 500mg",
                "generic_name": "Amoxicillin",
                "sku": "AMX-500",
                "barcode": "1234567890001",
                "category": "Antibiotics",
                "supplier": "MedSupply Co.",
                "cost_price": 5.00,
                "selling_price": 8.00,
                "mrp": 10.00,
                "low_stock_threshold": 50,
            },
            {
                "name": "Paracetamol 500mg",
                "generic_name": "Paracetamol",
                "sku": "PAR-500",
                "barcode": "1234567890002",
                "category": "Pain Relief",
                "supplier": "PharmaDirect Ltd.",
                "cost_price": 2.00,
                "selling_price": 3.50,
                "mrp": 4.00,
                "low_stock_threshold": 100,
            },
            {
                "name": "Vitamin C 1000mg",
                "generic_name": "Ascorbic Acid",
                "sku": "VTC-1000",
                "barcode": "1234567890003",
                "category": "Vitamins",
                "supplier": "HealthPlus Distributors",
                "cost_price": 8.00,
                "selling_price": 12.00,
                "mrp": 15.00,
                "low_stock_threshold": 30,
            },
            {
                "name": "Ibuprofen 400mg",
                "generic_name": "Ibuprofen",
                "sku": "IBU-400",
                "barcode": "1234567890004",
                "category": "Pain Relief",
                "supplier": "MedSupply Co.",
                "cost_price": 3.50,
                "selling_price": 6.00,
                "mrp": 7.50,
                "low_stock_threshold": 80,
            },
            {
                "name": "Cough Syrup 100ml",
                "generic_name": "Dextromethorphan",
                "sku": "CGH-100",
                "barcode": "1234567890005",
                "category": "Cold & Flu",
                "supplier": "PharmaDirect Ltd.",
                "cost_price": 6.00,
                "selling_price": 10.00,
                "mrp": 12.00,
                "low_stock_threshold": 25,
            },
        ]

        for prod_data in products_data:
            existing_prod = db.query(Product).filter(Product.sku == prod_data["sku"]).first()
            if not existing_prod:
                product = Product(
                    name=prod_data["name"],
                    generic_name=prod_data["generic_name"],
                    sku=prod_data["sku"],
                    barcode=prod_data["barcode"],
                    category_id=categories[prod_data["category"]],
                    supplier_id=suppliers[prod_data["supplier"]],
                    cost_price=prod_data["cost_price"],
                    selling_price=prod_data["selling_price"],
                    mrp=prod_data["mrp"],
                    low_stock_threshold=prod_data["low_stock_threshold"],
                    total_stock=0,  # Will be updated by batches
                )
                db.add(product)
                db.flush()

                # Add batches for each product
                batches = [
                    {
                        "batch_number": f"BATCH-{prod_data['sku']}-001",
                        "quantity": 100,
                        "manufacture_date": date.today() - timedelta(days=30),
                        "expiry_date": date.today() + timedelta(days=365),
                        "cost_price": prod_data["cost_price"],
                    },
                    {
                        "batch_number": f"BATCH-{prod_data['sku']}-002",
                        "batch_number": f"BATCH-{prod_data['sku']}-002",
                        "quantity": 50,
                        "manufacture_date": date.today() - timedelta(days=15),
                        "expiry_date": date.today() + timedelta(days=180),  # Expiring sooner
                        "cost_price": prod_data["cost_price"],
                    },
                ]

                total_stock = 0
                for batch_data in batches:
                    batch = ProductBatch(
                        product_id=product.id,
                        **batch_data
                    )
                    db.add(batch)
                    total_stock += batch_data["quantity"]

                product.total_stock = total_stock

        db.commit()
        print("✓ Products and batches created")

        print("\n✅ Database seeded successfully!")
        print("\nDefault Users:")
        print("  Admin    - username: admin    | password: admin123")
        print("  Manager  - username: manager  | password: manager123")
        print("  Cashier  - username: cashier  | password: cashier123")

    except Exception as e:
        print(f"\n❌ Error seeding database: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
