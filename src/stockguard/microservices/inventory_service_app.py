"""
Independent entrypoint for StockGuard Inventory Microservice.
Can be executed as: uvicorn stockguard.microservices.inventory_service_app:app --port 8001
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from stockguard.api.v1.inventory import router as inventory_router
from stockguard.api.v1.products import router as products_router
from stockguard.api.v1.reservations import router as reservations_router
from stockguard.api.v1.health import router as health_router

app = FastAPI(
    title="StockGuard - Inventory Service",
    version="1.0.0",
    description="Dedicated microservice managing Products, Stock Quantities, and Atomic Reservations"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1/health", tags=["Health"])
app.include_router(products_router, prefix="/api/v1/products", tags=["Products"])
app.include_router(inventory_router, prefix="/api/v1/inventory", tags=["Inventory"])
app.include_router(reservations_router, prefix="/api/v1/reservations", tags=["Reservations"])
