"""001_initial_schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-11-15 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Products
    op.create_table(
        'products',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('sku', sa.String(64), nullable=False, unique=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price', sa.Numeric(12, 2), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('price >= 0', name='chk_product_price_non_negative')
    )
    op.create_index('ix_products_sku', 'products', ['sku'], unique=True)

    # 2. Inventory Items
    op.create_table(
        'inventory_items',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('product_id', sa.String(36), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sku', sa.String(64), sa.ForeignKey('products.sku', ondelete='CASCADE'), nullable=False),
        sa.Column('available_stock', sa.Integer(), nullable=False, default=0),
        sa.Column('reserved_stock', sa.Integer(), nullable=False, default=0),
        sa.Column('allocated_stock', sa.Integer(), nullable=False, default=0),
        sa.Column('low_stock_threshold', sa.Integer(), nullable=False, default=10),
        sa.Column('version', sa.Integer(), nullable=False, default=1),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('available_stock >= 0', name='chk_inventory_available_non_negative'),
        sa.CheckConstraint('reserved_stock >= 0', name='chk_inventory_reserved_non_negative'),
        sa.CheckConstraint('allocated_stock >= 0', name='chk_inventory_allocated_non_negative'),
        sa.CheckConstraint('low_stock_threshold >= 0', name='chk_inventory_threshold_non_negative')
    )
    op.create_index('ix_inventory_items_product_id', 'inventory_items', ['product_id'], unique=True)
    op.create_index('ix_inventory_items_sku', 'inventory_items', ['sku'], unique=True)

    # 3. Reservations
    op.create_table(
        'reservations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('idempotency_key', sa.String(128), nullable=False, unique=True),
        sa.Column('order_id', sa.String(36), nullable=True),
        sa.Column('product_id', sa.String(36), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sku', sa.String(64), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('quantity > 0', name='chk_reservation_quantity_positive')
    )
    op.create_index('ix_reservations_idempotency_key', 'reservations', ['idempotency_key'], unique=True)
    op.create_index('ix_reservations_order_id', 'reservations', ['order_id'])
    op.create_index('ix_reservations_product_id', 'reservations', ['product_id'])
    op.create_index('ix_reservations_sku', 'reservations', ['sku'])
    op.create_index('ix_reservations_status', 'reservations', ['status'])
    op.create_index('ix_reservations_expires_at', 'reservations', ['expires_at'])

    # 4. Orders & Items
    op.create_table(
        'orders',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('order_number', sa.String(64), nullable=False, unique=True),
        sa.Column('customer_id', sa.String(64), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('total_amount', sa.Numeric(12, 2), nullable=False, default=0.00),
        sa.Column('currency', sa.String(3), nullable=False, default='USD'),
        sa.Column('idempotency_key', sa.String(128), nullable=True, unique=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('total_amount >= 0', name='chk_order_total_amount_non_negative')
    )
    op.create_index('ix_orders_order_number', 'orders', ['order_number'], unique=True)
    op.create_index('ix_orders_customer_id', 'orders', ['customer_id'])
    op.create_index('ix_orders_status', 'orders', ['status'])

    op.create_table(
        'order_items',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('order_id', sa.String(36), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
        sa.Column('product_id', sa.String(36), sa.ForeignKey('products.id'), nullable=False),
        sa.Column('sku', sa.String(64), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Numeric(12, 2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('quantity > 0', name='chk_order_item_quantity_positive'),
        sa.CheckConstraint('unit_price >= 0', name='chk_order_item_unit_price_non_negative')
    )
    op.create_index('ix_order_items_order_id', 'order_items', ['order_id'])

    # 5. Payments
    op.create_table(
        'payments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('order_id', sa.String(36), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, default='USD'),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('transaction_id', sa.String(128), nullable=True, unique=True),
        sa.Column('payment_method', sa.String(64), nullable=False, default='SIMULATED_CARD'),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('amount >= 0', name='chk_payment_amount_non_negative')
    )
    op.create_index('ix_payments_order_id', 'payments', ['order_id'], unique=True)

    # 6. Fulfillments
    op.create_table(
        'fulfillments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('order_id', sa.String(36), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('tracking_number', sa.String(128), nullable=True, unique=True),
        sa.Column('carrier', sa.String(64), nullable=True, default='SIM_CARRIER'),
        sa.Column('shipped_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)
    )
    op.create_index('ix_fulfillments_order_id', 'fulfillments', ['order_id'], unique=True)

    # 7. Outbox Messages
    op.create_table(
        'outbox_messages',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('event_type', sa.String(128), nullable=False),
        sa.Column('aggregate_type', sa.String(64), nullable=False),
        sa.Column('aggregate_id', sa.String(64), nullable=False),
        sa.Column('payload', sa.Text(), nullable=False),
        sa.Column('headers', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('retry_count', sa.Integer(), nullable=False, default=0),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)
    )
    op.create_index('ix_outbox_messages_event_type', 'outbox_messages', ['event_type'])
    op.create_index('ix_outbox_messages_status', 'outbox_messages', ['status'])

    # 8. Processed Events (Idempotent Consumers)
    op.create_table(
        'processed_events',
        sa.Column('id', sa.String(128), primary_key=True),
        sa.Column('consumer_name', sa.String(64), nullable=False),
        sa.Column('event_type', sa.String(128), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=False)
    )
    op.create_index('ix_processed_events_consumer_name', 'processed_events', ['consumer_name'])


def downgrade() -> None:
    op.drop_table('processed_events')
    op.drop_table('outbox_messages')
    op.drop_table('fulfillments')
    op.drop_table('payments')
    op.drop_table('order_items')
    op.drop_table('orders')
    op.drop_table('reservations')
    op.drop_table('inventory_items')
    op.drop_table('products')
