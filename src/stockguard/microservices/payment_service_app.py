"""
Independent entrypoint for StockGuard Payment Simulation Microservice.
Can be executed as: uvicorn stockguard.microservices.payment_service_app:app --port 8003
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from stockguard.api.v1.payments import router as payments_router
from stockguard.api.v1.health import router as health_router

app = FastAPI(
    title="StockGuard - Payment Service",
    version="1.0.0",
    description="Dedicated microservice managing Payment Authorizations and Simulating Transactions",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1/health", tags=["Health"])
app.include_router(payments_router, prefix="/api/v1/payments", tags=["Payments"])
