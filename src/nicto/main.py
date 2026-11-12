from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

import uvicorn
from fastapi import FastAPI

from nicto.adapters.api.router import api_router
from nicto.adapters.network.factory import create_network_controller
from nicto.adapters.persistence.database import create_engine, create_session_factory, reset_schema
from nicto.adapters.persistence.repositories import SqlaNetworkRepository
from nicto.adapters.persistence.unit_of_work import SqlaUnitOfWork
from nicto.adapters.presentation.factory import create_flexcurve_publisher
from nicto.application.use_cases.load_network import LoadNetworkUseCase
from nicto.config import Config
from nicto.dependencies import provide_flexcurve_publication, register_dependencies


def _create_lifespan(config: Config | None) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Create the database schema and load the network topology into it on startup."""
        resolved_config = Config.from_env() if config is None else config
        engine = create_engine(resolved_config.database_url)
        publisher = create_flexcurve_publisher(resolved_config)
        try:
            # Reset schema (drop + create) to ensure clean state
            await reset_schema(engine)

            session_factory = create_session_factory(engine)

            # The session context manager rolls back uncommitted work if loading fails
            async with session_factory() as session:
                await LoadNetworkUseCase(
                    repository=SqlaNetworkRepository(session),
                    controller=create_network_controller(resolved_config),
                    unit_of_work=SqlaUnitOfWork(session),
                ).execute()
                publication = provide_flexcurve_publication(session, resolved_config, publisher)
                if publication is not None:
                    await publication.publish_all()

            app.state.config = resolved_config
            app.state.session_factory = session_factory
            app.state.flexcurve_publisher = publisher
            yield
        finally:
            if publisher is not None:
                await publisher.close()
            await engine.dispose()

    return lifespan


def create_app(config: Config | None = None) -> FastAPI:
    """Build the FastAPI application, loading the configuration from the environment if none is given."""
    app = FastAPI(title="nicto", lifespan=_create_lifespan(config))
    app.include_router(api_router)
    register_dependencies(app)
    return app


def start() -> None:
    """Start the web application."""
    config = Config.from_env()
    uvicorn.run("nicto.main:create_app", factory=True, host=config.api_host, port=config.api_port, reload=False)


if __name__ == "__main__":
    start()
