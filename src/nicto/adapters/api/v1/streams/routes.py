from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from nicto.adapters.api.v1.streams.schemas import InsertStreamRequest, InsertStreamResponse
from nicto.application.use_cases.insert_stream import (
    InsertStreamUseCase,
    PortNotFoundError,
    StreamUnfeasibleError,
)

streams_router = APIRouter(prefix="/streams", tags=["streams"])


def get_insert_stream_use_case() -> InsertStreamUseCase:
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
