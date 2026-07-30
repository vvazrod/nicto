from abc import ABC, abstractmethod

from nicto.core.entities import Link, Node, Port, Stream
from pydantic_extra_types.mac_address import MacAddress


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
