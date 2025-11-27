"""
Seed script to populate database with sample data for testing.
Run this script after running migrations.
"""
import sys
import os
from datetime import datetime, date, timedelta

# Add backend directory to path
backend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend')
sys.path.insert(0, backend_dir)

from app.db.base import SessionLocal
from app.models.user import User, UserRole
from app.models.category import Category
from app.models.supplier import Supplier
from app.models.product import Product, ProductBatch, DosageForm, PrescriptionStatus
from app.core.security import get_password_hash


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
                "name": "Amoxicillin 500mg Capsules",
                "generic_name": "Amoxicillin",
                "sku": "AMX-500",
                "barcode": "1234567890001",
                "category": "Antibiotics",
                "supplier": "MedSupply Co.",
                "dosage_form": DosageForm.CAPSULE,
                "strength": "500mg",
                "prescription_status": PrescriptionStatus.PRESCRIPTION_REQUIRED,
                "active_ingredient": "Amoxicillin Trihydrate",
                "manufacturer": "GlaxoPharm Ghana Ltd",
                "usage_instructions": "Take 1 capsule every 8 hours for 7-10 days, or as directed by physician",
                "side_effects": "Nausea, diarrhea, skin rash, allergic reactions",
                "contraindications": "Penicillin allergy, mononucleosis",
                "storage_conditions": "Store below 25°C in dry place",
                "cost_price": 5.00,
                "selling_price": 8.00,
                "wholesale_price": 6.50,
                "mrp": 10.00,
                "low_stock_threshold": 50,
                "reorder_level": 75,
                "reorder_quantity": 200,
            },
            {
                "name": "Paracetamol 500mg Tablets",
                "generic_name": "Paracetamol",
                "sku": "PAR-500",
                "barcode": "1234567890002",
                "category": "Pain Relief",
                "supplier": "PharmaDirect Ltd.",
                "dosage_form": DosageForm.TABLET,
                "strength": "500mg",
                "prescription_status": PrescriptionStatus.OTC,
                "active_ingredient": "Paracetamol",
                "manufacturer": "Ernest Chemists Ltd",
                "usage_instructions": "Take 1-2 tablets every 4-6 hours. Maximum 8 tablets in 24 hours",
                "side_effects": "Rare: skin rash, liver damage with overdose",
                "contraindications": "Severe liver disease",
                "storage_conditions": "Store below 30°C",
                "cost_price": 2.00,
                "selling_price": 3.50,
                "wholesale_price": 2.75,
                "mrp": 4.00,
                "low_stock_threshold": 100,
                "reorder_level": 150,
                "reorder_quantity": 500,
            },
            {
                "name": "Vitamin C 1000mg Tablets",
                "generic_name": "Ascorbic Acid",
                "sku": "VTC-1000",
                "barcode": "1234567890003",
                "category": "Vitamins",
                "supplier": "HealthPlus Distributors",
                "dosage_form": DosageForm.TABLET,
                "strength": "1000mg",
                "prescription_status": PrescriptionStatus.OTC,
                "active_ingredient": "Ascorbic Acid",
                "manufacturer": "Ayrton Drug Manufacturing Ltd",
                "usage_instructions": "Take 1 tablet daily with food",
                "side_effects": "Mild: upset stomach, diarrhea at high doses",
                "contraindications": "Kidney stones history",
                "storage_conditions": "Store in cool, dry place below 25°C",
                "cost_price": 8.00,
                "selling_price": 12.00,
                "wholesale_price": 10.00,
                "mrp": 15.00,
                "low_stock_threshold": 30,
                "reorder_level": 50,
                "reorder_quantity": 150,
            },
            {
                "name": "Ibuprofen 400mg Tablets",
                "generic_name": "Ibuprofen",
                "sku": "IBU-400",
                "barcode": "1234567890004",
                "category": "Pain Relief",
                "supplier": "MedSupply Co.",
                "dosage_form": DosageForm.TABLET,
                "strength": "400mg",
                "prescription_status": PrescriptionStatus.OTC,
                "active_ingredient": "Ibuprofen",
                "manufacturer": "Danadams Pharmaceutical",
                "usage_instructions": "Take 1 tablet every 6-8 hours with food. Maximum 3 tablets daily",
                "side_effects": "Stomach upset, heartburn, dizziness, headache",
                "contraindications": "Stomach ulcers, severe heart disease, third trimester pregnancy",
                "storage_conditions": "Store below 25°C",
                "cost_price": 3.50,
                "selling_price": 6.00,
                "wholesale_price": 4.75,
                "mrp": 7.50,
                "low_stock_threshold": 80,
                "reorder_level": 120,
                "reorder_quantity": 300,
            },
            {
                "name": "Cough Syrup 100ml",
                "generic_name": "Dextromethorphan",
                "sku": "CGH-100",
                "barcode": "1234567890005",
                "category": "Cold & Flu",
                "supplier": "PharmaDirect Ltd.",
                "dosage_form": DosageForm.SYRUP,
                "strength": "15mg/5ml",
                "prescription_status": PrescriptionStatus.OTC,
                "active_ingredient": "Dextromethorphan HBr",
                "manufacturer": "LaGray Chemical Company",
                "usage_instructions": "Adults: 10ml every 6 hours. Children 6-12yrs: 5ml every 6 hours",
                "side_effects": "Drowsiness, dizziness, nausea",
                "contraindications": "Children under 6, MAO inhibitor use",
                "storage_conditions": "Store below 25°C, do not freeze",
                "cost_price": 6.00,
                "selling_price": 10.00,
                "wholesale_price": 8.00,
                "mrp": 12.00,
                "low_stock_threshold": 25,
                "reorder_level": 40,
                "reorder_quantity": 100,
            },
            {
                "name": "Artemether Injection 80mg/ml",
                "generic_name": "Artemether",
                "sku": "ART-80",
                "barcode": "1234567890006",
                "category": "Antibiotics",
                "supplier": "MedSupply Co.",
                "dosage_form": DosageForm.INJECTION,
                "strength": "80mg/ml",
                "prescription_status": PrescriptionStatus.PRESCRIPTION_REQUIRED,
                "active_ingredient": "Artemether",
                "manufacturer": "Kinapharma Ltd",
                "usage_instructions": "For severe malaria. Administer by deep intramuscular injection as prescribed",
                "side_effects": "Injection site pain, nausea, dizziness, QT prolongation",
                "contraindications": "First trimester pregnancy, severe liver disease",
                "storage_conditions": "Store at 2-8°C, protect from light",
                "requires_id": True,
                "cost_price": 15.00,
                "selling_price": 25.00,
                "wholesale_price": 20.00,
                "mrp": 30.00,
                "low_stock_threshold": 20,
                "reorder_level": 30,
                "reorder_quantity": 80,
            },
            {
                "name": "Ciprofloxacin 500mg Tablets",
                "generic_name": "Ciprofloxacin",
                "sku": "CIP-500",
                "barcode": "1234567890007",
                "category": "Antibiotics",
                "supplier": "PharmaDirect Ltd.",
                "dosage_form": DosageForm.TABLET,
                "strength": "500mg",
                "prescription_status": PrescriptionStatus.PRESCRIPTION_REQUIRED,
                "active_ingredient": "Ciprofloxacin HCl",
                "manufacturer": "Ernest Chemists Ltd",
                "usage_instructions": "Take 1 tablet twice daily for 7-14 days",
                "side_effects": "Nausea, diarrhea, dizziness, tendon rupture risk",
                "contraindications": "Children under 18, pregnancy, tendon disorders",
                "storage_conditions": "Store below 25°C",
                "cost_price": 4.50,
                "selling_price": 7.50,
                "wholesale_price": 6.00,
                "mrp": 9.00,
                "low_stock_threshold": 60,
                "reorder_level": 80,
                "reorder_quantity": 200,
            },
            {
                "name": "Metformin 500mg Tablets",
                "generic_name": "Metformin",
                "sku": "MET-500",
                "barcode": "1234567890008",
                "category": "Digestive Health",
                "supplier": "MedSupply Co.",
                "dosage_form": DosageForm.TABLET,
                "strength": "500mg",
                "prescription_status": PrescriptionStatus.PRESCRIPTION_REQUIRED,
                "active_ingredient": "Metformin HCl",
                "manufacturer": "GlaxoPharm Ghana Ltd",
                "usage_instructions": "Take 1-2 tablets twice daily with meals",
                "side_effects": "Nausea, diarrhea, metallic taste, vitamin B12 deficiency",
                "contraindications": "Severe kidney disease, metabolic acidosis",
                "storage_conditions": "Store below 30°C",
                "cost_price": 3.00,
                "selling_price": 5.50,
                "wholesale_price": 4.25,
                "mrp": 7.00,
                "low_stock_threshold": 70,
                "reorder_level": 100,
                "reorder_quantity": 250,
            },
            {
                "name": "Omeprazole 20mg Capsules",
                "generic_name": "Omeprazole",
                "sku": "OME-20",
                "barcode": "1234567890009",
                "category": "Digestive Health",
                "supplier": "HealthPlus Distributors",
                "dosage_form": DosageForm.CAPSULE,
                "strength": "20mg",
                "prescription_status": PrescriptionStatus.OTC,
                "active_ingredient": "Omeprazole",
                "manufacturer": "Ayrton Drug Manufacturing Ltd",
                "usage_instructions": "Take 1 capsule daily before breakfast",
                "side_effects": "Headache, diarrhea, stomach pain, nausea",
                "contraindications": "Known hypersensitivity",
                "storage_conditions": "Store below 25°C in dry place",
                "cost_price": 5.50,
                "selling_price": 9.00,
                "wholesale_price": 7.25,
                "mrp": 11.00,
                "low_stock_threshold": 50,
                "reorder_level": 75,
                "reorder_quantity": 150,
            },
            {
                "name": "Antibiotic Ointment 15g",
                "generic_name": "Neomycin/Polymyxin B",
                "sku": "NEO-15",
                "barcode": "1234567890010",
                "category": "Skin Care",
                "supplier": "PharmaDirect Ltd.",
                "dosage_form": DosageForm.OINTMENT,
                "strength": "5mg/10000U per g",
                "prescription_status": PrescriptionStatus.OTC,
                "active_ingredient": "Neomycin Sulfate, Polymyxin B",
                "manufacturer": "Danadams Pharmaceutical",
                "usage_instructions": "Apply thin layer to affected area 1-3 times daily",
                "side_effects": "Skin irritation, redness, allergic reaction",
                "contraindications": "Large skin areas, deep wounds",
                "storage_conditions": "Store below 25°C",
                "cost_price": 6.50,
                "selling_price": 11.00,
                "wholesale_price": 8.75,
                "mrp": 13.00,
                "low_stock_threshold": 35,
                "reorder_level": 50,
                "reorder_quantity": 100,
            },
            {
                "name": "Bandages (Assorted) 10pk",
                "generic_name": "Adhesive Bandages",
                "sku": "BND-AST",
                "barcode": "1234567890011",
                "category": "First Aid",
                "supplier": "HealthPlus Distributors",
                "dosage_form": DosageForm.OTHER,
                "strength": "Various sizes",
                "prescription_status": PrescriptionStatus.OTC,
                "active_ingredient": "N/A",
                "manufacturer": "LaGray Chemical Company",
                "usage_instructions": "Clean wound, apply bandage, change daily or when wet",
                "side_effects": "Rare: skin irritation from adhesive",
                "contraindications": "None",
                "storage_conditions": "Store in dry place",
                "cost_price": 2.50,
                "selling_price": 4.50,
                "wholesale_price": 3.50,
                "mrp": 5.50,
                "low_stock_threshold": 100,
                "reorder_level": 150,
                "reorder_quantity": 400,
            },
            {
                "name": "Cetirizine 10mg Tablets",
                "generic_name": "Cetirizine",
                "sku": "CET-10",
                "barcode": "1234567890012",
                "category": "Cold & Flu",
                "supplier": "MedSupply Co.",
                "dosage_form": DosageForm.TABLET,
                "strength": "10mg",
                "prescription_status": PrescriptionStatus.OTC,
                "active_ingredient": "Cetirizine Dihydrochloride",
                "manufacturer": "Ernest Chemists Ltd",
                "usage_instructions": "Take 1 tablet daily for allergies",
                "side_effects": "Drowsiness, dry mouth, headache",
                "contraindications": "Severe kidney disease",
                "storage_conditions": "Store below 30°C",
                "cost_price": 3.20,
                "selling_price": 5.50,
                "wholesale_price": 4.35,
                "mrp": 7.00,
                "low_stock_threshold": 55,
                "reorder_level": 80,
                "reorder_quantity": 200,
            },
            {
                "name": "Aspirin 75mg Tablets",
                "generic_name": "Acetylsalicylic Acid",
                "sku": "ASP-75",
                "barcode": "1234567890013",
                "category": "Pain Relief",
                "supplier": "PharmaDirect Ltd.",
                "dosage_form": DosageForm.TABLET,
                "strength": "75mg",
                "prescription_status": PrescriptionStatus.OTC,
                "active_ingredient": "Acetylsalicylic Acid",
                "manufacturer": "GlaxoPharm Ghana Ltd",
                "usage_instructions": "Take 1 tablet daily with food for cardiovascular protection",
                "side_effects": "Stomach upset, bleeding risk, allergic reactions",
                "contraindications": "Bleeding disorders, children under 16, stomach ulcers",
                "storage_conditions": "Store below 25°C in dry place",
                "cost_price": 1.80,
                "selling_price": 3.20,
                "wholesale_price": 2.50,
                "mrp": 4.00,
                "low_stock_threshold": 90,
                "reorder_level": 120,
                "reorder_quantity": 350,
            },
            {
                "name": "Multivitamin Tablets",
                "generic_name": "Multivitamin Complex",
                "sku": "MVT-DLY",
                "barcode": "1234567890014",
                "category": "Vitamins",
                "supplier": "HealthPlus Distributors",
                "dosage_form": DosageForm.TABLET,
                "strength": "Daily Formula",
                "prescription_status": PrescriptionStatus.OTC,
                "active_ingredient": "Vitamins A, B, C, D, E, K, Minerals",
                "manufacturer": "Ayrton Drug Manufacturing Ltd",
                "usage_instructions": "Take 1 tablet daily with meal",
                "side_effects": "Rare: upset stomach, allergic reaction",
                "contraindications": "Vitamin overdose risk if taking other supplements",
                "storage_conditions": "Store in cool, dry place",
                "cost_price": 7.50,
                "selling_price": 12.50,
                "wholesale_price": 10.00,
                "mrp": 15.00,
                "low_stock_threshold": 40,
                "reorder_level": 60,
                "reorder_quantity": 150,
            },
            {
                "name": "Diclofenac Gel 50g",
                "generic_name": "Diclofenac Sodium",
                "sku": "DIC-GEL",
                "barcode": "1234567890015",
                "category": "Pain Relief",
                "supplier": "MedSupply Co.",
                "dosage_form": DosageForm.CREAM,
                "strength": "1% w/w",
                "prescription_status": PrescriptionStatus.OTC,
                "active_ingredient": "Diclofenac Sodium",
                "manufacturer": "Danadams Pharmaceutical",
                "usage_instructions": "Apply to affected area 3-4 times daily, massage gently",
                "side_effects": "Skin irritation, redness, rash",
                "contraindications": "Broken skin, aspirin allergy, third trimester pregnancy",
                "storage_conditions": "Store below 25°C",
                "cost_price": 8.00,
                "selling_price": 13.50,
                "wholesale_price": 10.75,
                "mrp": 16.00,
                "low_stock_threshold": 30,
                "reorder_level": 45,
                "reorder_quantity": 100,
            },
        ]

        for prod_data in products_data:
            existing_prod = db.query(Product).filter(Product.sku == prod_data["sku"]).first()
            if not existing_prod:
                # Extract category and supplier names
                category_name = prod_data.pop("category")
                supplier_name = prod_data.pop("supplier")

                # Create product with all fields
                product = Product(
                    **prod_data,
                    category_id=categories[category_name],
                    supplier_id=suppliers[supplier_name],
                    total_stock=0,  # Will be updated by batches
                )
                db.add(product)
                db.flush()

                # Add batches for each product with varying expiry dates and stock levels
                # Create different batch scenarios to meet user requirements
                product_index = len([p for p in db.query(Product).all()])

                if product_index % 3 == 0:
                    # Low stock with near expiry (critical)
                    batches = [
                        {
                            "batch_number": f"BATCH-{product.sku}-001",
                            "quantity": 5,  # Very low stock
                            "manufacture_date": date.today() - timedelta(days=300),
                            "expiry_date": date.today() + timedelta(days=15),  # Expiring in 15 days (critical)
                            "cost_price": product.cost_price,
                            "location": "Shelf A1",
                        },
                    ]
                elif product_index % 3 == 1:
                    # Low stock with warning expiry
                    batches = [
                        {
                            "batch_number": f"BATCH-{product.sku}-001",
                            "quantity": 8,  # Low stock
                            "manufacture_date": date.today() - timedelta(days=200),
                            "expiry_date": date.today() + timedelta(days=25),  # Expiring in 25 days (warning)
                            "cost_price": product.cost_price,
                            "location": "Shelf B1",
                        },
                        {
                            "batch_number": f"BATCH-{product.sku}-002",
                            "quantity": 10,
                            "manufacture_date": date.today() - timedelta(days=100),
                            "expiry_date": date.today() + timedelta(days=60),
                            "cost_price": product.cost_price,
                            "location": "Shelf B2",
                        },
                    ]
                else:
                    # Normal stock with mixed expiry dates
                    batches = [
                        {
                            "batch_number": f"BATCH-{product.sku}-001",
                            "quantity": 80,
                            "manufacture_date": date.today() - timedelta(days=60),
                            "expiry_date": date.today() + timedelta(days=365),
                            "cost_price": product.cost_price,
                            "location": "Shelf C1",
                        },
                        {
                            "batch_number": f"BATCH-{product.sku}-002",
                            "quantity": 50,
                            "manufacture_date": date.today() - timedelta(days=30),
                            "expiry_date": date.today() + timedelta(days=180),
                            "cost_price": product.cost_price,
                            "location": "Shelf C2",
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
