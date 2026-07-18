"""druckauftrag_bezeichnung

Revision ID: f4a1b2c3d4e5
Revises: 2c7393097a67
Create Date: 2026-07-17 16:10:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'f4a1b2c3d4e5'
down_revision = '2c7393097a67'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('druckauftrag', schema=None) as batch_op:
        batch_op.add_column(sa.Column('bezeichnung', sa.String(length=200), nullable=False, server_default=''))


def downgrade() -> None:
    with op.batch_alter_table('druckauftrag', schema=None) as batch_op:
        batch_op.drop_column('bezeichnung')
