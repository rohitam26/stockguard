"""
Independent entrypoint for StockGuard Fulfillment Microservice.
Can be executed as: uvicorn stockguard.microservices.fulfillment_service_app:app --port 8004
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from stockguard.api.v1.fulfillment import router as fulfillment_router
from stockguard.api.v1.health import router as health_router

app = FastAPI(
    title="StockGuard - Fulfillment Service",
    version="1.0.0",
    description="Dedicated microservice managing Order Packaging, Shipment Tracking, and Final Delivery"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1/health", tags=["Health"])
app.include_router(fulfillment_router, prefix="/api/v1/fulfillment", tags=["Fulfillment"])
