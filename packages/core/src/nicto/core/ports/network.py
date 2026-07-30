from abc import ABC, abstractmethod

from nicto.core.entities import Link, Node


class NetworkController(ABC):
    """Abstract base class for network controllers."""

    @abstractmethod
    async def get_topology(self) -> tuple[list[Node], list[Link]]:
        """Get the network topology."""
