import logging
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from stockguard.models.product import Product
from stockguard.models.inventory import InventoryItem
from stockguard.schemas.product import ProductCreate, ProductUpdate
from stockguard.schemas.inventory import InventoryAdjustRequest
from stockguard.services.outbox_service import OutboxService

logger = logging.getLogger("stockguard.inventory_service")


class ProductNotFoundException(Exception):
    pass


class SkuAlreadyExistsException(Exception):
    pass


class InsufficientStockException(Exception):
    pass


class InventoryService:
    @staticmethod
    def create_product(db: Session, req: ProductCreate) -> Product:
        # Check SKU uniqueness
        existing = db.execute(select(Product).where(Product.sku == req.sku)).scalar_one_or_none()
        if existing:
            raise SkuAlreadyExistsException(f"Product with SKU '{req.sku}' already exists.")

        product = Product(
            sku=req.sku,
            name=req.name,
            description=req.description,
            price=req.price
        )
        db.add(product)
        db.flush()  # Obtain product.id

        inventory = InventoryItem(
            product_id=product.id,
            sku=product.sku,
            available_stock=req.initial_stock,
            reserved_stock=0,
            allocated_stock=0,
            low_stock_threshold=req.low_stock_threshold
        )
        db.add(inventory)

        # Transactional outbox event
        OutboxService.create_message(
            db=db,
            event_type="product.created",
            aggregate_type="product",
            aggregate_id=product.id,
            payload={
                "id": product.id,
                "sku": product.sku,
                "name": product.name,
                "price": str(product.price),
                "initial_stock": req.initial_stock
            }
        )

        db.commit()
        db.refresh(product)
        logger.info("Created product SKU: %s, initial stock: %d", product.sku, req.initial_stock)
        return product

    @staticmethod
    def get_product_by_id(db: Session, product_id: str) -> Product:
        product = db.execute(select(Product).where(Product.id == product_id)).scalar_one_or_none()
        if not product:
            raise ProductNotFoundException(f"Product with ID '{product_id}' not found.")
        return product

    @staticmethod
    def get_product_by_sku(db: Session, sku: str) -> Product:
        product = db.execute(select(Product).where(Product.sku == sku)).scalar_one_or_none()
        if not product:
            raise ProductNotFoundException(f"Product with SKU '{sku}' not found.")
        return product

    @staticmethod
    def list_products(
        db: Session,
        skip: int = 0,
        limit: int = 500,
        active_only: bool = True
    ) -> list[Product]:
        query = select(Product)
        if active_only:
            query = query.where(Product.is_active.is_(True))
        query = query.offset(skip).limit(limit).order_by(Product.created_at.desc())
        return list(db.execute(query).scalars().all())

    @staticmethod
    def update_product(db: Session, product_id: str, req: ProductUpdate) -> Product:
        product = InventoryService.get_product_by_id(db, product_id)
        if req.name is not None:
            product.name = req.name
        if req.description is not None:
            product.description = req.description
        if req.price is not None:
            product.price = req.price
        if req.is_active is not None:
            product.is_active = req.is_active

        if req.low_stock_threshold is not None:
            inv = db.execute(
                select(InventoryItem).where(InventoryItem.product_id == product.id)
            ).scalar_one_or_none()
            if inv:
                inv.low_stock_threshold = req.low_stock_threshold

        db.commit()
        db.refresh(product)
        return product

    @staticmethod
    def get_inventory_by_sku(db: Session, sku: str) -> InventoryItem:
        inv = db.execute(select(InventoryItem).where(InventoryItem.sku == sku)).scalar_one_or_none()
        if not inv:
            raise ProductNotFoundException(f"Inventory record for SKU '{sku}' not found.")
        return inv

    @staticmethod
    def list_inventory(
        db: Session,
        skip: int = 0,
        limit: int = 500
    ) -> list[InventoryItem]:
        query = select(InventoryItem).offset(skip).limit(limit).order_by(InventoryItem.created_at.desc())
        return list(db.execute(query).scalars().all())

    @staticmethod
    def adjust_inventory(db: Session, req: InventoryAdjustRequest) -> InventoryItem:
        """
        Adjust available inventory by delta (positive or negative).
        Atomically ensures available_stock + delta >= 0 using conditional UPDATE.
        """
        if req.quantity_delta < 0:
            abs_deduction = abs(req.quantity_delta)
            # Atomic conditional update
            stmt = (
                update(InventoryItem)
                .where(
                    InventoryItem.sku == req.sku,
                    InventoryItem.available_stock >= abs_deduction
                )
                .values(
                    available_stock=InventoryItem.available_stock + req.quantity_delta,
                    version=InventoryItem.version + 1
                )
            )
            result = db.execute(stmt)
            if result.rowcount == 0:
                # Check if product exists
                inv = db.execute(
                    select(InventoryItem).where(InventoryItem.sku == req.sku)
                ).scalar_one_or_none()
                if not inv:
                    raise ProductNotFoundException(f"Inventory for SKU '{req.sku}' not found.")
                raise InsufficientStockException(
                    f"Insufficient stock for SKU '{req.sku}'. Requested deduction: {abs_deduction}, Available: {inv.available_stock}"
                )
        else:
            stmt = (
                update(InventoryItem)
                .where(InventoryItem.sku == req.sku)
                .values(
                    available_stock=InventoryItem.available_stock + req.quantity_delta,
                    version=InventoryItem.version + 1
                )
            )
            result = db.execute(stmt)
            if result.rowcount == 0:
                raise ProductNotFoundException(f"Inventory for SKU '{req.sku}' not found.")

        inv = db.execute(
            select(InventoryItem).where(InventoryItem.sku == req.sku)
        ).scalar_one()

        OutboxService.create_message(
            db=db,
            event_type="inventory.adjusted",
            aggregate_type="inventory",
            aggregate_id=inv.id,
            payload={
                "sku": req.sku,
                "quantity_delta": req.quantity_delta,
                "reason": req.reason,
                "new_available_stock": inv.available_stock
            }
        )

        db.commit()
        db.refresh(inv)
        logger.info(
            "Adjusted SKU %s by delta %d. Available: %d, reason: %s",
            req.sku,
            req.quantity_delta,
            inv.available_stock,
            req.reason
        )
        return inv
