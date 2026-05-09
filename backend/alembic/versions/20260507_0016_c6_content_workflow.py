# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Add C6 content workflow revisions and SEO metadata."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = '20260507_0016'
down_revision = '20260507_0014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create additive content workflow metadata and revision history."""

    op.add_column(
        'pragma_content_entries',
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
    )
    op.add_column(
        'pragma_content_entries',
        sa.Column('seo_title', sa.String(length=70), nullable=True),
    )
    op.add_column(
        'pragma_content_entries',
        sa.Column('seo_description', sa.String(length=320), nullable=True),
    )
    op.add_column(
        'pragma_content_entries',
        sa.Column('seo_canonical_url', sa.String(length=2048), nullable=True),
    )
    op.add_column(
        'pragma_content_entries',
        sa.Column('seo_robots', sa.String(length=32), nullable=False, server_default='index'),
    )
    op.add_column(
        'pragma_content_entries',
        sa.Column('seo_og_title', sa.String(length=95), nullable=True),
    )
    op.add_column(
        'pragma_content_entries',
        sa.Column('seo_og_description', sa.String(length=300), nullable=True),
    )
    op.add_column(
        'pragma_content_entries',
        sa.Column('seo_og_image', sa.String(length=2048), nullable=True),
    )
    op.create_check_constraint(
        'ck_pragma_content_entries_version_positive',
        'pragma_content_entries',
        'version >= 1',
    )
    op.create_check_constraint(
        'ck_pragma_content_entries_seo_robots',
        'pragma_content_entries',
        "seo_robots IN ('index', 'noindex')",
    )

    op.create_table(
        'pragma_content_entry_revisions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entry_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('revision_number', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=16), nullable=False),
        sa.Column('slug', sa.String(length=160), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('seo_metadata', postgresql.JSONB(), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('restore_source_revision_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            'revision_number >= 1',
            name='ck_pragma_content_entry_revisions_number_positive',
        ),
        sa.CheckConstraint(
            "action IN ('create', 'update', 'publish', 'unpublish', 'restore')",
            name='ck_pragma_content_entry_revisions_action',
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name='ck_pragma_content_entry_revisions_status',
        ),
        sa.ForeignKeyConstraint(
            ['entry_id'],
            ['pragma_content_entries.id'],
            name='fk_pragma_content_entry_revisions_entry_id',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['created_by_user_id'],
            ['pragma_users.id'],
            name='fk_pragma_content_entry_revisions_created_by_user_id',
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['restore_source_revision_id'],
            ['pragma_content_entry_revisions.id'],
            name='fk_pragma_content_entry_revisions_restore_source',
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name='pk_pragma_content_entry_revisions'),
        sa.UniqueConstraint(
            'entry_id',
            'revision_number',
            name='uq_pragma_content_entry_revisions_entry_number',
        ),
    )
    op.create_index(
        'ix_pragma_content_entry_revisions_entry_created',
        'pragma_content_entry_revisions',
        ['entry_id', 'created_at'],
        unique=False,
    )


def downgrade() -> None:
    """Drop C6 content workflow metadata and revision history."""

    op.drop_index(
        'ix_pragma_content_entry_revisions_entry_created',
        table_name='pragma_content_entry_revisions',
    )
    op.drop_table('pragma_content_entry_revisions')
    op.drop_constraint(
        'ck_pragma_content_entries_seo_robots',
        'pragma_content_entries',
        type_='check',
    )
    op.drop_constraint(
        'ck_pragma_content_entries_version_positive',
        'pragma_content_entries',
        type_='check',
    )
    op.drop_column('pragma_content_entries', 'seo_og_image')
    op.drop_column('pragma_content_entries', 'seo_og_description')
    op.drop_column('pragma_content_entries', 'seo_og_title')
    op.drop_column('pragma_content_entries', 'seo_robots')
    op.drop_column('pragma_content_entries', 'seo_canonical_url')
    op.drop_column('pragma_content_entries', 'seo_description')
    op.drop_column('pragma_content_entries', 'seo_title')
    op.drop_column('pragma_content_entries', 'version')
