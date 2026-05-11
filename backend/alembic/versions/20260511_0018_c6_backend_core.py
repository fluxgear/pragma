# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Add C6 autosave activity and scheduling tables."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = '20260511_0018'
down_revision = '20260507_0017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create additive backend-core workflow tables."""

    op.create_table(
        'pragma_content_entry_autosaves',
        sa.Column('entry_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('base_version', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(length=160), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('seo_metadata', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            'base_version >= 1',
            name='ck_pragma_content_entry_autosaves_base_version_positive',
        ),
        sa.ForeignKeyConstraint(
            ['entry_id'],
            ['pragma_content_entries.id'],
            name='fk_pragma_content_entry_autosaves_entry_id',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['user_id'],
            ['pragma_users.id'],
            name='fk_pragma_content_entry_autosaves_user_id',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint(
            'entry_id',
            'user_id',
            name='pk_pragma_content_entry_autosaves',
        ),
    )
    op.create_index(
        'ix_pragma_content_entry_autosaves_user_updated',
        'pragma_content_entry_autosaves',
        ['user_id', 'updated_at'],
        unique=False,
    )

    op.create_table(
        'pragma_content_entry_activity',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entry_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content_type_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('entry_slug', sa.String(length=160), nullable=True),
        sa.Column('entry_version', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=32), nullable=False),
        sa.Column('actor_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            'details',
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            'entry_version IS NULL OR entry_version >= 1',
            name='ck_pragma_content_entry_activity_version_positive',
        ),
        sa.CheckConstraint(
            "action IN ("
            "'create', 'update', 'autosave', 'publish', 'unpublish', "
            "'restore', 'preview', 'delete', 'schedule_set', "
            "'schedule_cancel', 'schedule_execute', 'schedule_fail'"
            ")",
            name='ck_pragma_content_entry_activity_action',
        ),
        sa.ForeignKeyConstraint(
            ['actor_user_id'],
            ['pragma_users.id'],
            name='fk_pragma_content_entry_activity_actor_user_id',
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name='pk_pragma_content_entry_activity'),
    )
    op.create_index(
        'ix_pragma_content_entry_activity_entry_created',
        'pragma_content_entry_activity',
        ['entry_id', 'created_at'],
        unique=False,
    )
    op.create_index(
        'ix_pragma_content_entry_activity_action_created',
        'pragma_content_entry_activity',
        ['action', 'created_at'],
        unique=False,
    )

    op.create_table(
        'pragma_content_entry_schedules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entry_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(length=16), nullable=False),
        sa.Column('run_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('requested_entry_version', sa.Integer(), nullable=False),
        sa.Column('requested_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('state', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failure_code', sa.String(length=64), nullable=True),
        sa.Column('failure_detail', sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "action IN ('publish', 'unpublish')",
            name='ck_pragma_content_entry_schedules_action',
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'executed', 'cancelled', 'failed')",
            name='ck_pragma_content_entry_schedules_state',
        ),
        sa.CheckConstraint(
            'requested_entry_version >= 1',
            name='ck_pragma_content_entry_schedules_version_positive',
        ),
        sa.ForeignKeyConstraint(
            ['requested_by_user_id'],
            ['pragma_users.id'],
            name='fk_pragma_content_entry_schedules_requested_by_user_id',
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name='pk_pragma_content_entry_schedules'),
    )
    op.create_index(
        'ix_pragma_content_entry_schedules_entry_state',
        'pragma_content_entry_schedules',
        ['entry_id', 'state'],
        unique=False,
    )
    op.create_index(
        'ix_pragma_content_entry_schedules_due',
        'pragma_content_entry_schedules',
        ['state', 'run_at'],
        unique=False,
    )
    op.create_index(
        'uq_pragma_content_entry_schedules_pending_action',
        'pragma_content_entry_schedules',
        ['entry_id', 'action'],
        unique=True,
        postgresql_where=sa.text("state = 'pending'"),
    )


def downgrade() -> None:
    """Drop C6 backend-core workflow tables."""

    op.drop_index(
        'uq_pragma_content_entry_schedules_pending_action',
        table_name='pragma_content_entry_schedules',
    )
    op.drop_index(
        'ix_pragma_content_entry_schedules_due',
        table_name='pragma_content_entry_schedules',
    )
    op.drop_index(
        'ix_pragma_content_entry_schedules_entry_state',
        table_name='pragma_content_entry_schedules',
    )
    op.drop_table('pragma_content_entry_schedules')
    op.drop_index(
        'ix_pragma_content_entry_activity_action_created',
        table_name='pragma_content_entry_activity',
    )
    op.drop_index(
        'ix_pragma_content_entry_activity_entry_created',
        table_name='pragma_content_entry_activity',
    )
    op.drop_table('pragma_content_entry_activity')
    op.drop_index(
        'ix_pragma_content_entry_autosaves_user_updated',
        table_name='pragma_content_entry_autosaves',
    )
    op.drop_table('pragma_content_entry_autosaves')
