from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from nicto.adapters.api.v1.streams.schemas import InsertStreamRequest, InsertStreamResponse
from nicto.application.use_cases.insert_stream import (
    InsertStreamUseCase,
    PortNotFoundError,
    StreamUnfeasibleError,
)
from nicto.application.use_cases.remove_stream import RemoveStreamUseCase, StreamNotFoundError
from nicto.domain.models import StreamID

streams_router = APIRouter(prefix="/streams", tags=["streams"])


def get_insert_stream_use_case() -> InsertStreamUseCase:
    """Provide the use case; the application must override this dependency."""
    raise NotImplementedError


def get_remove_stream_use_case() -> RemoveStreamUseCase:
    """Provide the use case; the application must override this dependency."""
    raise NotImplementedError


@streams_router.post("", status_code=status.HTTP_201_CREATED)
async def insert_stream_endpoint(
    request: InsertStreamRequest,
    use_case: Annotated[InsertStreamUseCase, Depends(get_insert_stream_use_case)],
) -> InsertStreamResponse:
    """Insert a stream, computing its path and schedule."""
    try:
        stream = await use_case.execute(request.to_domain())
    except PortNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except StreamUnfeasibleError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
    return InsertStreamResponse.from_domain(stream)


@streams_router.delete("/{stream_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_stream_endpoint(
    stream_id: str,
    use_case: Annotated[RemoveStreamUseCase, Depends(get_remove_stream_use_case)],
) -> None:
    """Remove a stream and its allocations."""
    try:
        parsed_id = StreamID.parse(stream_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
    try:
        await use_case.execute(parsed_id)
    except StreamNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
