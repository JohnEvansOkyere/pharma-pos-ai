"""
Alembic environment configuration.
"""
from logging.config import fileConfig
from sqlalchemy import pool
from alembic import context
import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.config import settings
from app.db.base import Base

# Import all models for auto-generation
from app.models import (
    User,
    Category,
    Supplier,
    Product,
    ProductBatch,
    Sale,
    SaleItem,
    Notification,
    ActivityLog,
    RestoreDrill,
    StockAdjustment,
)

# this is the Alembic Config object
config = context.config

# Override sqlalchemy.url with settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    from sqlalchemy import text, create_engine, event
    
    db_url = config.get_main_option("sqlalchemy.url")
    
    # Optional database creation for first-time local setup. Normal migrations
    # should not require connecting to the default postgres database; managed or
    # Docker PostgreSQL deployments often restrict that connection.
    if os.getenv("ALEMBIC_CREATE_DATABASE", "false").lower() == "true" and db_url.startswith("postgresql://"):
        try:
            # Create engine to connect to default postgres database
            parts = db_url.split("/")
            temp_url = "/".join(parts[:-1]) + "/postgres"
            db_name = parts[-1]
            
            temp_engine = create_engine(temp_url, isolation_level="AUTOCOMMIT")
            with temp_engine.connect() as conn:
                try:
                    conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                    print(f"✅ Created database {db_name}")
                except Exception as e:
                    if "already exists" in str(e):
                        print(f"Database already exists")
                    else:
                        print(f"Could not create database: {e}")
            temp_engine.dispose()
        except Exception as e:
            print(f"Database creation attempt: {e}")
    
    connectable = create_engine(db_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
