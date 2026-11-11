from abc import ABC, abstractmethod

from pydantic_extra_types.mac_address import MacAddress

from nicto.domain.models import Link, Node, Port, Stream


class NetworkRepository(ABC):
    """Abstract repository to interact with persistent network data."""

    @abstractmethod
    async def create_link(self, link: Link) -> Link:
        """Persist a network link."""

    @abstractmethod
    async def create_node(self, node: Node) -> Node:
        """Persist a network node."""

    @abstractmethod
    async def get_port_by_mac(self, mac_address: MacAddress) -> Port | None:
        """Retrieve a network port identified by its MAC address, if present."""


class StreamRepository(ABC):
    """Abstract repository to interact with persistent stream data."""

    @abstractmethod
    async def create_stream(self, stream: Stream) -> Stream:
        """Persist a scheduled data stream."""


class UnitOfWork(ABC):
    """Abstract transaction boundary shared by the repositories of a use case."""

    @abstractmethod
    async def commit(self) -> None:
        """Make all pending repository changes permanent."""


class NetworkController(ABC):
    """Abstract base class for network controllers."""

    @abstractmethod
    async def get_topology(self) -> tuple[list[Node], list[Link]]:
        """Get the network topology."""
