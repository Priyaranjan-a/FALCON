"""Discovery: sources, scans, artefacts, occurrences and artefact links.

Revision ID: 0002_discovery
Revises: 0001_foundation
Created: 2026-09-28 17:18:32.336089
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
import falcon.kernel.database


revision: str = "0002_discovery"
down_revision: str | Sequence[str] | None = "0001_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('artefacts',
    sa.Column('system_id', sa.String(length=36), nullable=False),
    sa.Column('fingerprint', sa.String(length=40), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('name', sa.String(length=300), nullable=False),
    sa.Column('family', sa.String(length=80), nullable=True),
    sa.Column('identity', sa.JSON(), nullable=False),
    sa.Column('properties', sa.JSON(), nullable=False),
    sa.Column('quantum', sa.String(length=16), nullable=True),
    sa.Column('classical', sa.String(length=16), nullable=True),
    sa.Column('primitive', sa.String(length=32), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('occurrence_count', sa.Integer(), nullable=False),
    sa.Column('first_seen_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=False),
    sa.Column('last_seen_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=False),
    sa.Column('first_scan_id', sa.String(length=36), nullable=True),
    sa.Column('last_scan_id', sa.String(length=36), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.ForeignKeyConstraint(['system_id'], ['systems.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('system_id', 'fingerprint', name='uq_artefact_system_fingerprint')
    )
    with op.batch_alter_table('artefacts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_artefacts_classical'), ['classical'], unique=False)
        batch_op.create_index(batch_op.f('ix_artefacts_family'), ['family'], unique=False)
        batch_op.create_index(batch_op.f('ix_artefacts_kind'), ['kind'], unique=False)
        batch_op.create_index(batch_op.f('ix_artefacts_last_scan_id'), ['last_scan_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_artefacts_quantum'), ['quantum'], unique=False)
        batch_op.create_index(batch_op.f('ix_artefacts_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_artefacts_system_id'), ['system_id'], unique=False)

    op.create_table('sources',
    sa.Column('system_id', sa.String(length=36), nullable=False),
    sa.Column('kind', sa.String(length=24), nullable=False),
    sa.Column('name', sa.String(length=160), nullable=False),
    sa.Column('locator', sa.Text(), nullable=False),
    sa.Column('options', sa.JSON(), nullable=False),
    sa.Column('created_by', sa.String(length=36), nullable=True),
    sa.Column('last_scan_id', sa.String(length=36), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['system_id'], ['systems.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('sources', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sources_system_id'), ['system_id'], unique=False)

    op.create_table('artefact_links',
    sa.Column('from_id', sa.String(length=36), nullable=False),
    sa.Column('to_id', sa.String(length=36), nullable=False),
    sa.Column('relation', sa.String(length=32), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.ForeignKeyConstraint(['from_id'], ['artefacts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['to_id'], ['artefacts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('from_id', 'to_id', 'relation', name='uq_artefact_link')
    )
    with op.batch_alter_table('artefact_links', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_artefact_links_from_id'), ['from_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_artefact_links_to_id'), ['to_id'], unique=False)

    op.create_table('scans',
    sa.Column('source_id', sa.String(length=36), nullable=False),
    sa.Column('system_id', sa.String(length=36), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('stage', sa.String(length=16), nullable=True),
    sa.Column('stage_detail', sa.String(length=200), nullable=True),
    sa.Column('files_total', sa.Integer(), nullable=False),
    sa.Column('files_done', sa.Integer(), nullable=False),
    sa.Column('bytes_done', sa.BigInteger(), nullable=False),
    sa.Column('evidence_count', sa.Integer(), nullable=False),
    sa.Column('artefact_count', sa.Integer(), nullable=False),
    sa.Column('new_artefacts', sa.Integer(), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('requested_by', sa.String(length=36), nullable=True),
    sa.Column('requested_by_label', sa.String(length=160), nullable=True),
    sa.Column('cancel_requested', sa.Boolean(), nullable=False),
    sa.Column('queued_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=False),
    sa.Column('started_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=True),
    sa.Column('finished_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=True),
    sa.Column('coverage', sa.JSON(), nullable=True),
    sa.Column('stats', sa.JSON(), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['system_id'], ['systems.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('scans', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_scans_queued_at'), ['queued_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_scans_source_id'), ['source_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_scans_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_scans_system_id'), ['system_id'], unique=False)

    op.create_table('occurrences',
    sa.Column('artefact_id', sa.String(length=36), nullable=False),
    sa.Column('scan_id', sa.String(length=36), nullable=False),
    sa.Column('source_id', sa.String(length=36), nullable=False),
    sa.Column('path', sa.Text(), nullable=False),
    sa.Column('line', sa.Integer(), nullable=True),
    sa.Column('col', sa.Integer(), nullable=True),
    sa.Column('snippet', sa.JSON(), nullable=True),
    sa.Column('detector', sa.String(length=40), nullable=False),
    sa.Column('rule', sa.String(length=80), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('function', sa.String(length=40), nullable=True),
    sa.Column('via', sa.String(length=32), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.ForeignKeyConstraint(['artefact_id'], ['artefacts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['scan_id'], ['scans.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('occurrences', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_occurrences_artefact_id'), ['artefact_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_occurrences_scan_id'), ['scan_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('occurrences', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_occurrences_scan_id'))
        batch_op.drop_index(batch_op.f('ix_occurrences_artefact_id'))

    op.drop_table('occurrences')
    with op.batch_alter_table('scans', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_scans_system_id'))
        batch_op.drop_index(batch_op.f('ix_scans_status'))
        batch_op.drop_index(batch_op.f('ix_scans_source_id'))
        batch_op.drop_index(batch_op.f('ix_scans_queued_at'))

    op.drop_table('scans')
    with op.batch_alter_table('artefact_links', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_artefact_links_to_id'))
        batch_op.drop_index(batch_op.f('ix_artefact_links_from_id'))

    op.drop_table('artefact_links')
    with op.batch_alter_table('sources', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sources_system_id'))

    op.drop_table('sources')
    with op.batch_alter_table('artefacts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_artefacts_system_id'))
        batch_op.drop_index(batch_op.f('ix_artefacts_status'))
        batch_op.drop_index(batch_op.f('ix_artefacts_quantum'))
        batch_op.drop_index(batch_op.f('ix_artefacts_last_scan_id'))
        batch_op.drop_index(batch_op.f('ix_artefacts_kind'))
        batch_op.drop_index(batch_op.f('ix_artefacts_family'))
        batch_op.drop_index(batch_op.f('ix_artefacts_classical'))

    op.drop_table('artefacts')
