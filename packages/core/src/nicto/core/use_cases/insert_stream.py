from nicto.core.entities import Stream
from nicto.core.ports.persistence import StreamRepository


class InsertStreamUseCase:
    def __init__(self, repository: StreamRepository) -> None:
        self._repository = repository

    def execute(self, stream: Stream) -> dict:
        created_stream = self._repository.create_stream(stream)

        return {}
