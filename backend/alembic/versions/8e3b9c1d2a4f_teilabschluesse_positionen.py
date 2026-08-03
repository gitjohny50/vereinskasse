"""teilabschluesse_positionen

Revision ID: 8e3b9c1d2a4f
Revises: 2c7393097a67
Create Date: 2026-07-28 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '8e3b9c1d2a4f'
down_revision = '2c7393097a67'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('kassenabschluss', schema=None) as batch_op:
        batch_op.add_column(sa.Column('umfang_typ', sa.String(length=20), nullable=False, server_default='alle'))
        batch_op.add_column(sa.Column('umfang_beschreibung', sa.String(length=200), nullable=False, server_default='Alle offenen Positionen'))

    with op.batch_alter_table('verkaufsposition', schema=None) as batch_op:
        batch_op.add_column(sa.Column('abschluss_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_verkaufsposition_abschluss', 'kassenabschluss', ['abschluss_id'], ['id'])

    op.execute("""
        UPDATE verkaufsposition
        SET abschluss_id = (
            SELECT verkauf.abschluss_id
            FROM verkauf
            WHERE verkauf.id = verkaufsposition.verkauf_id
        )
        WHERE EXISTS (
            SELECT 1
            FROM verkauf
            WHERE verkauf.id = verkaufsposition.verkauf_id
              AND verkauf.abschluss_id IS NOT NULL
        )
    """)


def downgrade() -> None:
    with op.batch_alter_table('verkaufsposition', schema=None) as batch_op:
        batch_op.drop_constraint('fk_verkaufsposition_abschluss', type_='foreignkey')
        batch_op.drop_column('abschluss_id')

    with op.batch_alter_table('kassenabschluss', schema=None) as batch_op:
        batch_op.drop_column('umfang_beschreibung')
        batch_op.drop_column('umfang_typ')
