"""phase4_druckwarteschlange

Revision ID: 69b3ccccef42
Revises: d721d2ce1511
Create Date: 2026-07-16 04:54:22.688325
"""
from alembic import op
import sqlalchemy as sa


revision = '69b3ccccef42'
down_revision = 'd721d2ce1511'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Neue Spalten mit server_default, damit vorhandene Zeilen (Diagnose-Logs)
    # den NOT-NULL-Constraint erfüllen. Der Fremdschlüssel wird benannt (SQLite-Batch).
    with op.batch_alter_table('druckauftrag', schema=None) as batch_op:
        batch_op.add_column(sa.Column('max_versuche', sa.Integer(), nullable=False, server_default='3'))
        batch_op.add_column(sa.Column('aktualisiert_am', sa.DateTime(timezone=True),
                                      nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')))
        batch_op.add_column(sa.Column('verkauf_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('payload_b64', sa.Text(), nullable=False, server_default=''))
        batch_op.create_foreign_key('fk_druckauftrag_verkauf', 'verkauf', ['verkauf_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('druckauftrag', schema=None) as batch_op:
        batch_op.drop_constraint('fk_druckauftrag_verkauf', type_='foreignkey')
        batch_op.drop_column('payload_b64')
        batch_op.drop_column('verkauf_id')
        batch_op.drop_column('aktualisiert_am')
        batch_op.drop_column('max_versuche')
