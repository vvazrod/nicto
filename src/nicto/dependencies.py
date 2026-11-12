from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from sqlalchemy.ext.asyncio import AsyncSession

from nicto.adapters.api.v1.streams.routes import get_insert_stream_use_case, get_remove_stream_use_case
from nicto.adapters.persistence.database import create_db_session
from nicto.adapters.persistence.repositories import SqlaNetworkRepository, SqlaStreamRepository
from nicto.adapters.persistence.unit_of_work import SqlaUnitOfWork
from nicto.adapters.solvers.factory import create_path_solver, create_schedule_solver
from nicto.application.use_cases.insert_stream import InsertStreamUseCase
from nicto.application.use_cases.remove_stream import RemoveStreamUseCase
from nicto.config import Config


def get_config(request: Request) -> Config:
    """Return the configuration loaded at application startup."""
    return request.app.state.config


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session scoped to the request."""
    async for session in create_db_session(request.app.state.session_factory):
        yield session


def provide_insert_stream_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
    config: Annotated[Config, Depends(get_config)],
) -> InsertStreamUseCase:
    """Assemble the insert stream use case with its adapters."""
    return InsertStreamUseCase(
        network_repository=SqlaNetworkRepository(session),
        stream_repository=SqlaStreamRepository(session),
        unit_of_work=SqlaUnitOfWork(session),
        path_solver=create_path_solver(config),
        schedule_solver=create_schedule_solver(config),
        config=config,
    )


def provide_remove_stream_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RemoveStreamUseCase:
    """Assemble the remove stream use case with its adapters."""
    return RemoveStreamUseCase(
        stream_repository=SqlaStreamRepository(session),
        unit_of_work=SqlaUnitOfWork(session),
    )


def register_dependencies(app: FastAPI) -> None:
    """Bind the API's use case placeholders to their concrete providers."""
    app.dependency_overrides[get_insert_stream_use_case] = provide_insert_stream_use_case
    app.dependency_overrides[get_remove_stream_use_case] = provide_remove_stream_use_case
