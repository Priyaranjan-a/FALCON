"""Reports: the export library.

Revision ID: 0004_exports
Revises: 0003_reports
Created: 2026-09-29 09:20:49.181080
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
import falcon.kernel.database


revision: str = "0004_exports"
down_revision: str | Sequence[str] | None = "0003_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('report_exports',
    sa.Column('created_at', falcon.kernel.database.UTCDateTime(), nullable=False),
    sa.Column('created_by', sa.String(length=160), nullable=True),
    sa.Column('user_id', sa.String(length=36), nullable=True),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('format', sa.String(length=32), nullable=False),
    sa.Column('label', sa.String(length=160), nullable=False),
    sa.Column('scope', sa.String(length=200), nullable=False),
    sa.Column('system_id', sa.String(length=36), nullable=True),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('path', sa.Text(), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('report_exports', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_report_exports_created_at'), ['created_at'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('report_exports', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_report_exports_created_at'))

    op.drop_table('report_exports')
