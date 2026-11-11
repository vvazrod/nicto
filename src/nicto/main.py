from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from nicto.adapters.api.router import api_router
from nicto.adapters.api.v1.streams.routes import get_insert_stream_use_case
from nicto.adapters.network.factory import create_network_controller
from nicto.adapters.persistence.database import create_engine, create_schema, create_session_factory
from nicto.adapters.persistence.repositories import SqlaNetworkRepository
from nicto.adapters.persistence.unit_of_work import SqlaUnitOfWork
from nicto.application.use_cases.load_network import LoadNetworkUseCase
from nicto.config import Config
from nicto.dependencies import provide_insert_stream_use_case


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create the database and load the network topology into it on startup."""
    config = Config.from_env()
    engine = create_engine(config.database_url)
    await create_schema(engine)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        await LoadNetworkUseCase(
            repository=SqlaNetworkRepository(session),
            controller=create_network_controller(config),
            unit_of_work=SqlaUnitOfWork(session),
        ).execute()

    app.state.config = config
    app.state.session_factory = session_factory
    try:
        yield
    finally:
        await engine.dispose()


def create_app() -> FastAPI:
    """Build the FastAPI application."""
    app = FastAPI(title="nicto", lifespan=lifespan)
    app.include_router(api_router)
    app.dependency_overrides[get_insert_stream_use_case] = provide_insert_stream_use_case
    return app


app = create_app()


def start() -> None:
    """Start the web application."""
    uvicorn.run("nicto.main:app", host="0.0.0.0", port=8000, reload=False)  # noqa: S104


if __name__ == "__main__":
    start()
