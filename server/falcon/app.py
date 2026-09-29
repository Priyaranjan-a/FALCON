"""Application factory."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope

from . import __version__
from .domains.discovery.api import router as discovery_router
from .domains.horizon.api import router as horizon_router
from .domains.identity.api import auth as auth_router
from .domains.identity.api import members as members_router
from .domains.identity.api import tokens as tokens_router
from .domains.ledger.api import router as ledger_router
from .domains.organisation.api import organisation as organisation_router
from .domains.organisation.api import setup as setup_router
from .domains.overview.api import router as overview_router
from .domains.platform.api import router as platform_router
from .domains.risk.api import router as risk_router
from .domains.migration.api import router as migration_router
from .domains.reports.api import router as reports_router
from .domains.systems.api import router as systems_router
from .kernel import problems
from .kernel.http import HardeningMiddleware
from .kernel.problems import Problem
from .settings import get_settings

logger = logging.getLogger("falcon")


def configure_logging() -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s  %(message)s")


class ImmutableAssets(StaticFiles):
    """Hashed build assets never change, so browsers may cache them forever."""

    async def get_response(self, path: str, scope: Scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def _mount_console(app: FastAPI, dist: Path) -> None:
    index = dist / "index.html"
    if not index.is_file():
        logger.warning("console build not found at %s; serving the API only", dist)
        return
    if (dist / "assets").is_dir():
        app.mount("/assets", ImmutableAssets(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def console(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise Problem(404, "No such endpoint.")
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


def create_app(*, run_migrations: bool = True) -> FastAPI:
    settings = get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        import asyncio

        from .domains.discovery.runner import runner
        from .kernel.events import hub

        if run_migrations:
            from .kernel.migrate import upgrade

            upgrade()
        hub.bind(asyncio.get_running_loop())
        runner.start()
        if settings.demo:
            from .demo import seed

            try:
                seed()
            except Exception:  # noqa: BLE001 - the platform starts even if the demo cannot be created
                logger.exception("The demonstration data could not be created")
        logger.info("FALCON %s ready (%s)", __version__, settings.environment)
        try:
            yield
        finally:
            runner.stop()

    app = FastAPI(
        title="FALCON API",
        version=__version__,
        description="Post-quantum cryptographic discovery and migration intelligence.",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    problems.install(app)
    app.add_middleware(HardeningMiddleware, desktop=settings.desktop)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Content-Type", "Authorization", "X-Falcon-Request", "X-Request-ID"],
        )

    for router in (
        platform_router, setup_router, auth_router, members_router, tokens_router,
        organisation_router, horizon_router, systems_router, overview_router, ledger_router, discovery_router, risk_router, migration_router, reports_router,
    ):
        app.include_router(router)

    _mount_console(app, settings.console_dist)
    return app
