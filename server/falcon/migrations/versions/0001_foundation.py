"""Foundation schema: identity, organisation, systems register, audit ledger.

Revision ID: 0001_foundation
Revises: 
Created: 2026-09-28 11:35:23.300529
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
import falcon.kernel.database


revision: str = "0001_foundation"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('audit_events',
    sa.Column('seq', sa.BigInteger(), nullable=False),
    sa.Column('occurred_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=False),
    sa.Column('actor_id', sa.String(length=36), nullable=True),
    sa.Column('actor_label', sa.String(length=255), nullable=False),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('target_type', sa.String(length=32), nullable=True),
    sa.Column('target_id', sa.String(length=64), nullable=True),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('detail', sa.JSON(), nullable=True),
    sa.Column('ip', sa.String(length=64), nullable=True),
    sa.Column('prev_hash', sa.String(length=64), nullable=False),
    sa.Column('hash', sa.String(length=64), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('audit_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_events_action'), ['action'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_events_actor_id'), ['actor_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_events_occurred_at'), ['occurred_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_events_seq'), ['seq'], unique=True)
        batch_op.create_index(batch_op.f('ix_audit_events_target_id'), ['target_id'], unique=False)

    audit_head = op.create_table('audit_head',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('seq', sa.BigInteger(), nullable=False),
    sa.Column('hash', sa.String(length=64), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    # Genesis of the hash-chained audit ledger.
    op.bulk_insert(audit_head, [{"id": 1, "seq": 0, "hash": "0" * 64}])
    op.create_table('organisation',
    sa.Column('name', sa.String(length=160), nullable=False),
    sa.Column('sector', sa.String(length=48), nullable=False),
    sa.Column('country', sa.String(length=2), nullable=False),
    sa.Column('crqc_scenario', sa.String(length=16), nullable=False),
    sa.Column('crqc_median_year', sa.Float(), nullable=True),
    sa.Column('crqc_uncertainty', sa.String(length=16), nullable=True),
    sa.Column('risk_tolerance', sa.Float(), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('systems',
    sa.Column('code', sa.String(length=24), nullable=False),
    sa.Column('name', sa.String(length=160), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('kind', sa.String(length=24), nullable=False),
    sa.Column('lifecycle', sa.String(length=16), nullable=False),
    sa.Column('environment', sa.String(length=16), nullable=False),
    sa.Column('exposure', sa.String(length=16), nullable=False),
    sa.Column('criticality', sa.String(length=16), nullable=False),
    sa.Column('data_classification', sa.String(length=16), nullable=False),
    sa.Column('data_shelf_life_years', sa.Integer(), nullable=False),
    sa.Column('migration_years', sa.Float(), nullable=False),
    sa.Column('owner', sa.String(length=160), nullable=True),
    sa.Column('team', sa.String(length=160), nullable=True),
    sa.Column('tags', sa.JSON(), nullable=False),
    sa.Column('created_by', sa.String(length=36), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('systems', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_systems_code'), ['code'], unique=True)
        batch_op.create_index(batch_op.f('ix_systems_criticality'), ['criticality'], unique=False)
        batch_op.create_index(batch_op.f('ix_systems_data_classification'), ['data_classification'], unique=False)
        batch_op.create_index(batch_op.f('ix_systems_exposure'), ['exposure'], unique=False)
        batch_op.create_index(batch_op.f('ix_systems_kind'), ['kind'], unique=False)

    op.create_table('users',
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('role', sa.String(length=24), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=True),
    sa.Column('password_changed_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=True),
    sa.Column('failed_sign_ins', sa.Integer(), nullable=False),
    sa.Column('locked_until', falcon.kernel.database.UTCDateTime(timezone=True), nullable=True),
    sa.Column('last_sign_in_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=True),
    sa.Column('invited_by', sa.String(length=36), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)
        batch_op.create_index(batch_op.f('ix_users_role'), ['role'], unique=False)
        batch_op.create_index(batch_op.f('ix_users_status'), ['status'], unique=False)

    op.create_table('access_tokens',
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('prefix', sa.String(length=16), nullable=False),
    sa.Column('secret_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=False),
    sa.Column('expires_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=True),
    sa.Column('last_used_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=True),
    sa.Column('revoked_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('secret_hash')
    )
    with op.batch_alter_table('access_tokens', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_access_tokens_user_id'), ['user_id'], unique=False)

    op.create_table('invitations',
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('secret_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=False),
    sa.Column('expires_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=False),
    sa.Column('consumed_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.String(length=36), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('secret_hash')
    )
    with op.batch_alter_table('invitations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_invitations_user_id'), ['user_id'], unique=False)

    op.create_table('user_sessions',
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('secret_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=False),
    sa.Column('last_seen_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=False),
    sa.Column('expires_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', falcon.kernel.database.UTCDateTime(timezone=True), nullable=True),
    sa.Column('ip', sa.String(length=64), nullable=True),
    sa.Column('user_agent', sa.String(length=400), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('secret_hash')
    )
    with op.batch_alter_table('user_sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_sessions_user_id'), ['user_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('user_sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_sessions_user_id'))

    op.drop_table('user_sessions')
    with op.batch_alter_table('invitations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_invitations_user_id'))

    op.drop_table('invitations')
    with op.batch_alter_table('access_tokens', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_access_tokens_user_id'))

    op.drop_table('access_tokens')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_status'))
        batch_op.drop_index(batch_op.f('ix_users_role'))
        batch_op.drop_index(batch_op.f('ix_users_email'))

    op.drop_table('users')
    with op.batch_alter_table('systems', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_systems_kind'))
        batch_op.drop_index(batch_op.f('ix_systems_exposure'))
        batch_op.drop_index(batch_op.f('ix_systems_data_classification'))
        batch_op.drop_index(batch_op.f('ix_systems_criticality'))
        batch_op.drop_index(batch_op.f('ix_systems_code'))

    op.drop_table('systems')
    op.drop_table('organisation')
    op.drop_table('audit_head')
    with op.batch_alter_table('audit_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_events_target_id'))
        batch_op.drop_index(batch_op.f('ix_audit_events_seq'))
        batch_op.drop_index(batch_op.f('ix_audit_events_occurred_at'))
        batch_op.drop_index(batch_op.f('ix_audit_events_actor_id'))
        batch_op.drop_index(batch_op.f('ix_audit_events_action'))

    op.drop_table('audit_events')
