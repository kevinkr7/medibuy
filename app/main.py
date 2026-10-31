"""FastAPI application entry point."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import register_exception_handlers, router

DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def create_app() -> FastAPI:
    application = FastAPI(title="MediBuy", version="0.3.0")
    configured_origins = os.getenv("MEDIBUY_CORS_ORIGINS")
    origins = (
        [origin.strip() for origin in configured_origins.split(",") if origin.strip()]
        if configured_origins
        else list(DEFAULT_CORS_ORIGINS)
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    register_exception_handlers(application)
    application.include_router(router)
    return application


app = create_app()
