# ruff: noqa: ARG002
import pytest
from pydantic_extra_types.mac_address import MacAddress

from nicto.application.ports import (
    NetworkController,
    NetworkRepository,
    PathSolver,
    ScheduleSolver,
    StreamRepository,
    UnitOfWork,
)
from nicto.config import Config
from nicto.domain.models import Allocation, Hop, Link, Node, Port, Stream, StreamID


class MockNetworkRepository(NetworkRepository):
    """Mock network repository that records the operations performed on it."""

    def __init__(self) -> None:
        self.nodes: list[Node] = []
        self.links: list[Link] = []
        self.requested_mac_addresses: list[str] = []
        self.fail_node = False
        self.fail_link = False

    async def create_link(self, link: Link) -> Link:
        """Store the link, or raise when configured to fail."""
        if self.fail_link:
            msg = f"Failed to persist link between {link.port_a_mac_address} and {link.port_b_mac_address}"
            raise RuntimeError(msg)
        self.links.append(link)
        return link

    async def create_node(self, node: Node) -> Node:
        """Store the node, or raise when configured to fail."""
        if self.fail_node:
            msg = f"Failed to persist node {node.hostname}"
            raise RuntimeError(msg)
        self.nodes.append(node)
        return node

    async def get_port_by_mac(self, mac_address: MacAddress) -> Port | None:
        """Record the lookup and return the stored port with that MAC address, if any."""
        self.requested_mac_addresses.append(str(mac_address))
        for node in self.nodes:
            for port in node.ports:
                if port.mac_address == mac_address:
                    return port
        return None

    async def get_topology(self) -> tuple[list[Node], list[Link]]:
        """Return the stored nodes and links."""
        return self.nodes, self.links


class MockStreamRepository(StreamRepository):
    """Mock stream repository that records persisted streams."""

    def __init__(self) -> None:
        self.streams: list[Stream] = []

    async def create_stream(self, stream: Stream) -> Stream:
        """Record and return the stream."""
        self.streams.append(stream)
        return stream

    async def get_stream_by_id(self, stream_id: StreamID) -> Stream | None:
        """Return the recorded stream with that ID, if any."""
        return next((stream for stream in self.streams if stream.id == stream_id), None)

    async def delete_stream(self, stream_id: StreamID) -> None:
        """Forget the stream with that ID."""
        self.streams = [stream for stream in self.streams if stream.id != stream_id]


class MockUnitOfWork(UnitOfWork):
    """Mock unit of work that counts commits and rollbacks."""

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        """Count the commit."""
        self.commits += 1

    async def rollback(self) -> None:
        """Count the rollback."""
        self.rollbacks += 1


class MockNetworkController(NetworkController):
    """Mock network controller that returns a configurable topology."""

    def __init__(self) -> None:
        self.nodes: list[Node] = []
        self.links: list[Link] = []

    async def get_topology(self) -> tuple[list[Node], list[Link]]:
        """Get the configured topology."""
        return self.nodes, self.links


class MockPathSolver(PathSolver):
    """Mock path solver that returns a configurable path."""

    def __init__(self) -> None:
        self.path: list[Hop] = []

    def find_path(self, stream: Stream, nodes: list[Node], links: list[Link]) -> list[Hop]:
        """Return the configured path."""
        return self.path


class MockScheduleSolver(ScheduleSolver):
    """Mock schedule solver that returns configurable allocations."""

    def __init__(self) -> None:
        self.allocations: list[Allocation] = []

    def find_schedule(
        self,
        stream: Stream,
        path: list[Hop],
        config: Config,
    ) -> list[Allocation]:
        """Return the configured allocations."""
        return self.allocations


@pytest.fixture
def path_solver() -> MockPathSolver:
    """Mock path solver."""
    return MockPathSolver()


@pytest.fixture
def schedule_solver() -> MockScheduleSolver:
    """Mock schedule solver."""
    return MockScheduleSolver()


@pytest.fixture
def network_repository() -> MockNetworkRepository:
    """Mock network repository."""
    return MockNetworkRepository()


@pytest.fixture
def stream_repository() -> MockStreamRepository:
    """Mock stream repository."""
    return MockStreamRepository()


@pytest.fixture
def unit_of_work() -> MockUnitOfWork:
    """Mock unit of work."""
    return MockUnitOfWork()


@pytest.fixture
def network_controller() -> MockNetworkController:
    """Mock network controller."""
    return MockNetworkController()
