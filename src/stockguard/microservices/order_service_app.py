"""
Independent entrypoint for StockGuard Order & Saga Orchestration Microservice.
Can be executed as: uvicorn stockguard.microservices.order_service_app:app --port 8002
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from stockguard.api.v1.orders import router as orders_router
from stockguard.api.v1.health import router as health_router

app = FastAPI(
    title="StockGuard - Order Service",
    version="1.0.0",
    description="Dedicated microservice managing Customer Orders and Distributed Checkout Sagas"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1/health", tags=["Health"])
app.include_router(orders_router, prefix="/api/v1/orders", tags=["Orders"])
