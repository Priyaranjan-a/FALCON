"""Reports: signed CBOM snapshots.

Revision ID: 0003_reports
Revises: 0002_discovery
Created: 2026-09-29 02:59:50.910805
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
import falcon.kernel.database


revision: str = "0003_reports"
down_revision: str | Sequence[str] | None = "0002_discovery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('cbom_snapshots',
    sa.Column('created_at', falcon.kernel.database.UTCDateTime(), nullable=False),
    sa.Column('created_by', sa.String(length=160), nullable=True),
    sa.Column('system_id', sa.String(length=36), nullable=True),
    sa.Column('label', sa.String(length=160), nullable=False),
    sa.Column('digest', sa.String(length=64), nullable=False),
    sa.Column('components', sa.Integer(), nullable=False),
    sa.Column('summary', sa.JSON(), nullable=False),
    sa.Column('cbom', sa.Text(), nullable=False),
    sa.Column('envelope', sa.Text(), nullable=False),
    sa.Column('key_id', sa.String(length=64), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('cbom_snapshots', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_cbom_snapshots_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_cbom_snapshots_system_id'), ['system_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('cbom_snapshots', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_cbom_snapshots_system_id'))
        batch_op.drop_index(batch_op.f('ix_cbom_snapshots_created_at'))

    op.drop_table('cbom_snapshots')
