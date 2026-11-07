from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# app/main.py
from app.api.router import api_router
from app.api.routes import health

# app/api/routes/health.py
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title=settings.app_name, debug=settings.debug)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,  # needed for the refresh cookie in AGRAI-06
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(api_router, prefix=settings.api_prefix)

    return app


app = create_app()
