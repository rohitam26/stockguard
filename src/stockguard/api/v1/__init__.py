from fastapi import APIRouter
from stockguard.api.v1.products import router as products_router
from stockguard.api.v1.inventory import router as inventory_router
from stockguard.api.v1.reservations import router as reservations_router
from stockguard.api.v1.orders import router as orders_router
from stockguard.api.v1.payments import router as payments_router
from stockguard.api.v1.fulfillment import router as fulfillment_router
from stockguard.api.v1.health import router as health_router
from stockguard.api.v1.outbox import router as outbox_router

api_v1_router = APIRouter()
api_v1_router.include_router(health_router)
api_v1_router.include_router(products_router)
api_v1_router.include_router(inventory_router)
api_v1_router.include_router(reservations_router)
api_v1_router.include_router(orders_router)
api_v1_router.include_router(payments_router)
api_v1_router.include_router(fulfillment_router)
api_v1_router.include_router(outbox_router)

__all__ = ["api_v1_router"]
