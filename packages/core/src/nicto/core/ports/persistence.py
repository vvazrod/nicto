from abc import ABC, abstractmethod

from nicto.core.entities import Stream


class StreamRepository(ABC):
    @abstractmethod
    async def create_stream(self, stream: Stream) -> Stream:
        pass
