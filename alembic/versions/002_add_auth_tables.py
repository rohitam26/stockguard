"""002_add_auth_tables

Revision ID: 002_add_auth_tables
Revises: 001_initial_schema
Create Date: 2026-11-22 03:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '002_add_auth_tables'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Users
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('role', sa.String(32), nullable=False, default='CUSTOMER'),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_role', 'users', ['role'])

    # 2. Refresh Tokens
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)
    )
    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])
    op.create_index('ix_refresh_tokens_token_hash', 'refresh_tokens', ['token_hash'], unique=True)


def downgrade() -> None:
    op.drop_table('refresh_tokens')
    op.drop_table('users')
