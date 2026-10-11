"""FastAPI application entry point.

Creates the app, configures CORS, mounts uploads, registers routers, and unified exception handling.
Business logic belongs in routers/utils/services/tasks — not in main.py.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from backend.config import CORS_ORIGINS, UPLOAD_DIR
from backend.routers import (
    admin,
    admin_verification,
    ai,
    auth,
    customer,
    demo_fulfillment,
    provider,
    provider_verification,
    public,
    payment,
    marketplace,
    shared,
    websocket,
)
from backend.utils.errors import (
    general_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from backend.utils.response import success_response
from backend.utils.demo_ai_quota import dispose_demo_ai_quota_engines
from backend.services.health_service import readiness_status

Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

OPENAPI_TAGS = [
    {
        "name": "Auth",
        "description": "Registration, login, token refresh, logout, email and phone verification, and account security.",
    },
    {
        "name": "Public",
        "description": "Public endpoints (no login): provider listings, details, and reviews.",
    },
    {
        "name": "Customer",
        "description": "Customer-only endpoints: profile, favorites, bookings, payments, refunds, complaints, reviews.",
    },
    {
        "name": "Provider",
        "description": "Provider-only endpoints: profile, quotes, completion, refunds, and earnings.",
    },
    {
        "name": "Payment",
        "description": "iyzico Sandbox payment callbacks and payment-provider integration.",
    },
    {
        "name": "Marketplace",
        "description": "Provider payout details and local validation.",
    },
    {
        "name": "Admin",
        "description": "Admin-only endpoints: users, provider verification, complaints, reviews, and platform stats.",
    },
    {
        "name": "Shared",
        "description": "Multi-role endpoints: chat messages, notifications, booking details, and status history.",
    },
    {
        "name": "AI",
        "description": "AI chat, recommendations, async tasks, and vector search.",
    },
    {
        "name": "WebSocket",
        "description": "Real-time chat connections for chat room message delivery.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        dispose_demo_ai_quota_engines()


app = FastAPI(
    title="Workshop AI Backend API",
    description=(
        "Workshop AI backend API. See `docs/backend-api-standard.md` for conventions."
    ),
    version="0.1.0",
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)


def _normalize_file_schemas(value):
    """Make FastAPI's OpenAPI 3.1 file schemas render in Swagger UI.

    Pydantic emits ``contentMediaType`` for UploadFile values under OpenAPI
    3.1. Swagger UI versions used by local deployments do not consistently
    turn that representation into a file picker, especially for arrays. The
    endpoint still receives real multipart UploadFile values; this only adds
    the widely-supported ``format: binary`` hint to the generated contract.
    """

    if isinstance(value, dict):
        if value.get("contentMediaType") == "application/octet-stream":
            value.pop("contentMediaType", None)
            value["format"] = "binary"
        for child in value.values():
            _normalize_file_schemas(child)
    elif isinstance(value, list):
        for child in value:
            _normalize_file_schemas(child)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    app.openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=OPENAPI_TAGS,
    )
    _normalize_file_schemas(app.openapi_schema)
    return app.openapi_schema


app.openapi = custom_openapi

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

app.include_router(auth.router)
app.include_router(public.router)
app.include_router(customer.router)
app.include_router(provider.router)
app.include_router(demo_fulfillment.router)
app.include_router(provider_verification.router)
app.include_router(payment.router)
app.include_router(marketplace.router)
app.include_router(admin.router)
app.include_router(admin_verification.router)
app.include_router(shared.router)
app.include_router(ai.router)
app.include_router(websocket.router)


@app.get("/")
def home():
    return success_response(message="Workshop AI backend is running")


@app.get("/health")
def health_check():
    return success_response(
        {
            "status": "ok",
            "service": "Workshop AI backend",
        }
    )


@app.get("/ready")
def readiness_check():
    status = readiness_status()
    return JSONResponse(
        content=success_response(status),
        status_code=200 if status["ready"] else 503,
    )
