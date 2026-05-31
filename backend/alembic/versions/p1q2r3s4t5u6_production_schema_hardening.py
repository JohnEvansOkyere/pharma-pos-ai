"""production schema hardening

- Drop global unique constraints on products.sku, products.barcode,
  users.username, users.email
- Add composite unique constraints scoped to organization_id
  (local_pos installs with organization_id=NULL still work via COALESCE)
- Add composite indexes for common multi-tenant query patterns
  (CONCURRENTLY, so they run without locking in prod)
- Add set_updated_at() trigger function + per-table triggers

Revision ID: p1q2r3s4t5u6
Revises: o5d6e7f8g9h0
Create Date: 2026-05-29

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'p1q2r3s4t5u6'
down_revision = 'o5d6e7f8g9h0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    # ── 1. Composite unique constraints on products ───────────────────────────
    # Drop old global unique constraints (PG auto-names them <table>_<col>_key).
    # IF EXISTS prevents errors if they were already dropped.
    op.execute("ALTER TABLE products DROP CONSTRAINT IF EXISTS products_sku_key")
    op.execute("ALTER TABLE products DROP CONSTRAINT IF EXISTS products_barcode_key")

    if dialect == "postgresql":
        # Check PostgreSQL version for NULLS NOT DISTINCT support (PG 15+)
        pg_ver = conn.execute(sa.text("SHOW server_version_num")).scalar()
        pg_ver_num = int(pg_ver) if pg_ver else 0
        has_nulls_not_distinct = pg_ver_num >= 150000

        if has_nulls_not_distinct:
            # Two pharmacies with org=NULL and the same SKU are still unique
            op.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_products_org_sku
                ON products (organization_id, sku)
                NULLS NOT DISTINCT
            """)
            op.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_products_org_barcode
                ON products (organization_id, barcode)
                NULLS NOT DISTINCT
                WHERE barcode IS NOT NULL
            """)
        else:
            # PG < 15: use COALESCE to treat NULL org as sentinel -1
            op.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_products_org_sku
                ON products (COALESCE(organization_id, -1), sku)
            """)
            op.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_products_org_barcode
                ON products (COALESCE(organization_id, -1), barcode)
                WHERE barcode IS NOT NULL
            """)
    # SQLite (test env): skip — SQLite doesn't support partial or expression indexes
    # in the same way; rely on application-layer enforcement.

    # ── 2. Composite unique constraints on users ──────────────────────────────
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_username_key")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_key")

    if dialect == "postgresql":
        pg_ver = conn.execute(sa.text("SHOW server_version_num")).scalar()
        pg_ver_num = int(pg_ver) if pg_ver else 0
        has_nulls_not_distinct = pg_ver_num >= 150000

        if has_nulls_not_distinct:
            op.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_users_org_username
                ON users (organization_id, username)
                NULLS NOT DISTINCT
            """)
            op.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_users_org_email
                ON users (organization_id, email)
                NULLS NOT DISTINCT
                WHERE email IS NOT NULL
            """)
        else:
            op.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_users_org_username
                ON users (COALESCE(organization_id, -1), username)
            """)
            op.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_users_org_email
                ON users (COALESCE(organization_id, -1), email)
                WHERE email IS NOT NULL
            """)

    # ── 3. Composite performance indexes (CONCURRENTLY = no table lock) ───────
    # IMPORTANT: CREATE INDEX CONCURRENTLY cannot run inside a transaction.
    # We commit the current transaction first, then run each index creation
    # in AUTOCOMMIT mode, then resume normal transaction mode.
    if dialect == "postgresql":
        # Commit the open transaction so CONCURRENTLY is allowed
        op.get_bind().execute(sa.text("COMMIT"))

        concurrent_indexes = [
            # Sales — most queried by org + date
            (
                "ix_sales_org_created",
                "sales (organization_id, created_at DESC)",
            ),
            (
                "ix_sales_org_status_created",
                "sales (organization_id, status, created_at DESC)",
            ),
            # Products — catalog search in multi-tenant mode
            (
                "ix_products_org_active_name",
                "products (organization_id, is_active, name)",
            ),
            # Customers — retention queries
            (
                "ix_customers_org_active",
                "customers (organization_id, is_active)",
            ),
            # Follow-ups — scheduler hourly query
            (
                "ix_follow_ups_org_status_sched",
                "customer_follow_ups (organization_id, status, scheduled_at)",
            ),
            # Inventory movements — stock velocity reports
            (
                "ix_inv_movements_product_type_created",
                "inventory_movements (product_id, movement_type, created_at)",
            ),
        ]

        for idx_name, idx_on in concurrent_indexes:
            op.get_bind().execute(sa.text(
                f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {idx_name} ON {idx_on}"
            ))

        # Resume explicit transactions for the rest of the migration
        op.get_bind().execute(sa.text("BEGIN"))

    # ── 4. updated_at trigger (PostgreSQL only) ────────────────────────────────
    if dialect == "postgresql":
        op.execute("""
            CREATE OR REPLACE FUNCTION set_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW() AT TIME ZONE 'UTC';
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)

        for table in ("products", "users", "customers", "branches", "organizations"):
            trigger_name = f"trg_{table}_updated_at"
            op.execute(f"""
                DROP TRIGGER IF EXISTS {trigger_name} ON {table};
                CREATE TRIGGER {trigger_name}
                BEFORE UPDATE ON {table}
                FOR EACH ROW EXECUTE FUNCTION set_updated_at();
            """)


def downgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    # Drop triggers and function
    if dialect == "postgresql":
        for table in ("products", "users", "customers", "branches", "organizations"):
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")
        op.execute("DROP FUNCTION IF EXISTS set_updated_at()")

    # Drop composite indexes
    for idx in (
        "ix_inv_movements_product_type_created",
        "ix_follow_ups_org_status_sched",
        "ix_customers_org_active",
        "ix_products_org_active_name",
        "ix_sales_org_status_created",
        "ix_sales_org_created",
        "uq_users_org_email",
        "uq_users_org_username",
        "uq_products_org_barcode",
        "uq_products_org_sku",
    ):
        op.execute(f"DROP INDEX IF EXISTS {idx}")

    # Restore original global unique constraints
    if dialect == "postgresql":
        op.execute("ALTER TABLE products ADD CONSTRAINT products_sku_key UNIQUE (sku)")
        op.execute("ALTER TABLE products ADD CONSTRAINT products_barcode_key UNIQUE (barcode)")
        op.execute("ALTER TABLE users ADD CONSTRAINT users_username_key UNIQUE (username)")
        op.execute("ALTER TABLE users ADD CONSTRAINT users_email_key UNIQUE (email)")
