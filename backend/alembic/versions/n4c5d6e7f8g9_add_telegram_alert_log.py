"""add telegram alert log

Revision ID: n4c5d6e7f8g9
Revises: m3b4c5d6e7f8
Create Date: 2026-05-19 22:00:00

Stores one deduplication row per (organization, alert_key) so proactive
Telegram alerts are not re-sent within the configured cooldown window.
"""
from alembic import op
import sqlalchemy as sa

revision = 'n4c5d6e7f8g9'
down_revision = 'm3b4c5d6e7f8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'telegram_alert_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('alert_key', sa.String(length=200), nullable=False),
        sa.Column('last_sent_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'alert_key', name='uq_telegram_alert_logs_org_key'),
    )
    op.create_index('ix_telegram_alert_logs_id', 'telegram_alert_logs', ['id'])
    op.create_index('ix_telegram_alert_logs_organization_id', 'telegram_alert_logs', ['organization_id'])
    op.create_index('ix_telegram_alert_logs_alert_key', 'telegram_alert_logs', ['alert_key'])
    op.create_index('ix_telegram_alert_logs_last_sent_at', 'telegram_alert_logs', ['last_sent_at'])


def downgrade() -> None:
    op.drop_index('ix_telegram_alert_logs_last_sent_at', table_name='telegram_alert_logs')
    op.drop_index('ix_telegram_alert_logs_alert_key', table_name='telegram_alert_logs')
    op.drop_index('ix_telegram_alert_logs_organization_id', table_name='telegram_alert_logs')
    op.drop_index('ix_telegram_alert_logs_id', table_name='telegram_alert_logs')
    op.drop_table('telegram_alert_logs')
