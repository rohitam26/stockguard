import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from stockguard.config import get_settings
from stockguard.database import get_engine
from stockguard.models import init_db
from stockguard.messaging.rabbitmq import rabbitmq_client
from stockguard.api.v1 import api_v1_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("stockguard")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure Database Schema is created
    logger.info("Starting StockGuard %s...", settings.VERSION)
    engine = get_engine()
    init_db(engine)
    logger.info("Database tables and integrity constraints verified.")

    # Try connecting to RabbitMQ
    rabbitmq_client.connect()

    yield

    # Shutdown
    logger.info("StockGuard shutting down.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Enterprise Distributed Inventory Engine with Transactional Outbox and Distributed Saga Orchestration",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handler for structured JSON errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception processing %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error_type": type(exc).__name__, "message": str(exc)}
    )

# API Routers
app.include_router(api_v1_router, prefix=settings.API_V1_STR)

# Static Files & Dashboard Mount
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
async def serve_dashboard():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "StockGuard API is running. Dashboard assets not found."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("stockguard.main:app", host="0.0.0.0", port=8000, reload=True)
