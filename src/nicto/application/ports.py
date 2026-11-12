from abc import ABC, abstractmethod
from collections.abc import Sequence

from pydantic_extra_types.mac_address import MacAddress

from nicto.config import Config
from nicto.domain.models import Allocation, Hop, Link, Node, Port, Stream, StreamID


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

    @abstractmethod
    async def get_topology(self) -> tuple[list[Node], list[Link]]:
        """Retrieve all persisted nodes, with their ports' allocations, and links."""


class StreamRepository(ABC):
    """Abstract repository to interact with persistent stream data."""

    @abstractmethod
    async def create_stream(self, stream: Stream) -> Stream:
        """Persist a scheduled data stream."""

    @abstractmethod
    async def get_stream_by_id(self, stream_id: StreamID) -> Stream | None:
        """Retrieve a stream, with its allocations, by ID, if present."""

    @abstractmethod
    async def delete_stream(self, stream_id: StreamID) -> None:
        """Delete a stream and its allocations."""


class UnitOfWork(ABC):
    """Abstract transaction boundary shared by the repositories of a use case."""

    @abstractmethod
    async def commit(self) -> None:
        """Make all pending repository changes permanent."""

    @abstractmethod
    async def rollback(self) -> None:
        """Discard all pending repository changes."""


class NetworkController(ABC):
    """Abstract base class for network controllers."""

    @abstractmethod
    async def get_topology(self) -> tuple[list[Node], list[Link]]:
        """Get the network topology."""


class PathSolver(ABC):
    """Abstract base class for path solvers."""

    @abstractmethod
    def find_path(self, stream: Stream, nodes: list[Node], links: list[Link]) -> list[Hop]:
        """Find a feasible path for a stream in a topology, as ordered hops from source to destination.

        Each hop holds the egress port, with its existing allocations, and the link it transmits on.
        """


class ScheduleSolver(ABC):
    """Abstract base class for schedule solvers."""

    @abstractmethod
    def find_schedule(
        self,
        stream: Stream,
        path: list[Hop],
        config: Config,
    ) -> list[Allocation]:
        """Find feasible allocations for a stream along a path, given the allocations of its egress ports."""


class FlexcurvePublisher(ABC):
    """Abstract base class for presentation backends that publish the flexcurve of a port."""

    @abstractmethod
    async def publish_flexcurve(self, port_mac_address: MacAddress, flexcurve: Sequence[int]) -> None:
        """Publish the flexcurve of a port, where element ``i`` is the number of start positions for ``i + 1`` slots."""

    async def close(self) -> None:  # noqa: B027
        """Release the resources held by the backend."""
