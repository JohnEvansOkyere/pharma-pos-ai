"""add customer retention tables

Revision ID: o5d6e7f8g9h0
Revises: n4c5d6e7f8g9
Create Date: 2026-05-28 10:00:00

Adds:
  - customers table  (registered pharmacy customers, org-scoped)
  - customer_follow_ups table  (scheduled health follow-up messages)
  - sales.customer_id  FK -> customers.id (nullable)
  - sales.receipt_sent  boolean (digital receipt dispatched flag)
"""
from alembic import op
import sqlalchemy as sa

revision = 'o5d6e7f8g9h0'
down_revision = 'n4c5d6e7f8g9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── customers ────────────────────────────────────────────────────────────
    op.create_table(
        'customers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('branch_id', sa.Integer(), nullable=True),
        sa.Column('full_name', sa.String(length=150), nullable=False),
        sa.Column('phone', sa.String(length=30), nullable=False),
        sa.Column('email', sa.String(length=200), nullable=True),
        sa.Column('date_of_birth', sa.String(length=20), nullable=True),
        sa.Column('gender', sa.String(length=20), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('town', sa.String(length=100), nullable=True),
        sa.Column('region', sa.String(length=100), nullable=True),
        sa.Column('known_allergies', sa.Text(), nullable=True),
        sa.Column('chronic_conditions', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column(
            'sms_consent',
            sa.Enum('granted', 'declined', 'pending', name='consentstatus'),
            nullable=False,
            server_default='pending',
        ),
        sa.Column(
            'whatsapp_consent',
            sa.Enum('granted', 'declined', 'pending', name='consentstatus'),
            nullable=False,
            server_default='pending',
        ),
        sa.Column('consent_recorded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('preferred_channel', sa.String(length=20), nullable=False, server_default='sms'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_customers_id', 'customers', ['id'])
    op.create_index('ix_customers_organization_id', 'customers', ['organization_id'])
    op.create_index('ix_customers_branch_id', 'customers', ['branch_id'])
    op.create_index('ix_customers_phone', 'customers', ['phone'])
    # Unique phone per organization — de-duplication key
    op.create_index(
        'uq_customers_org_phone',
        'customers',
        ['organization_id', 'phone'],
        unique=True,
    )

    # ── customer_follow_ups ───────────────────────────────────────────────────
    op.create_table(
        'customer_follow_ups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('branch_id', sa.Integer(), nullable=True),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('sale_id', sa.Integer(), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('channel', sa.String(length=20), nullable=False),
        sa.Column(
            'status',
            sa.Enum('pending', 'sent', 'delivered', 'failed', 'skipped', 'responded',
                    name='followupstatus'),
            nullable=False,
            server_default='pending',
        ),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('provider_message_id', sa.String(length=200), nullable=True),
        sa.Column('message_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id']),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['sale_id'], ['sales.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_customer_follow_ups_id', 'customer_follow_ups', ['id'])
    op.create_index('ix_customer_follow_ups_organization_id', 'customer_follow_ups', ['organization_id'])
    op.create_index('ix_customer_follow_ups_customer_id', 'customer_follow_ups', ['customer_id'])
    op.create_index('ix_customer_follow_ups_sale_id', 'customer_follow_ups', ['sale_id'])
    op.create_index('ix_customer_follow_ups_scheduled_at', 'customer_follow_ups', ['scheduled_at'])
    op.create_index('ix_customer_follow_ups_status', 'customer_follow_ups', ['status'])

    # ── sales: add customer_id FK and receipt_sent flag ───────────────────────
    op.add_column('sales', sa.Column('customer_id', sa.Integer(), nullable=True))
    op.create_index('ix_sales_customer_id', 'sales', ['customer_id'])
    op.create_foreign_key(
        'fk_sales_customer_id',
        'sales', 'customers',
        ['customer_id'], ['id'],
    )
    op.add_column(
        'sales',
        sa.Column('receipt_sent', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )


def downgrade() -> None:
    op.drop_constraint('fk_sales_customer_id', 'sales', type_='foreignkey')
    op.drop_index('ix_sales_customer_id', table_name='sales')
    op.drop_column('sales', 'receipt_sent')
    op.drop_column('sales', 'customer_id')

    op.drop_index('ix_customer_follow_ups_status', table_name='customer_follow_ups')
    op.drop_index('ix_customer_follow_ups_scheduled_at', table_name='customer_follow_ups')
    op.drop_index('ix_customer_follow_ups_sale_id', table_name='customer_follow_ups')
    op.drop_index('ix_customer_follow_ups_customer_id', table_name='customer_follow_ups')
    op.drop_index('ix_customer_follow_ups_organization_id', table_name='customer_follow_ups')
    op.drop_index('ix_customer_follow_ups_id', table_name='customer_follow_ups')
    op.drop_table('customer_follow_ups')

    op.drop_index('uq_customers_org_phone', table_name='customers')
    op.drop_index('ix_customers_phone', table_name='customers')
    op.drop_index('ix_customers_branch_id', table_name='customers')
    op.drop_index('ix_customers_organization_id', table_name='customers')
    op.drop_index('ix_customers_id', table_name='customers')
    op.drop_table('customers')

    op.execute('DROP TYPE IF EXISTS followupstatus')
    op.execute('DROP TYPE IF EXISTS consentstatus')
