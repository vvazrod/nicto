import asyncio

import pytest
from nicto.core.adapters.persistence.in_memory import InMemoryNetworkRepository
from nicto.core.entities import Link, Node, Port
from nicto.core.ports.network import NetworkController
from nicto.core.use_cases.load_network import LoadNetworkUseCase

NODES = [
    Node(
        hostname="switch-a",
        ports=[Port(mac_address="00:11:22:33:44:55", name="eth0")],
    ),
    Node(
        hostname="switch-b",
        ports=[Port(mac_address="00:11:22:33:44:56", name="eth0")],
    ),
]
LINKS = [
    Link(
        port_a_mac_address="00:11:22:33:44:55",
        port_b_mac_address="00:11:22:33:44:56",
        speed=1000,
        propagation_delay=10,
    ),
]


class TestNetworkController(NetworkController):
    """Return a fixed topology for use-case tests."""

    async def get_topology(self) -> tuple[list[Node], list[Link]]:
        """Get the fixed topology."""
        return NODES, LINKS


class FailingNetworkRepository(InMemoryNetworkRepository):
    """Return a different entity to simulate failed persistence."""

    def __init__(self, *, fail_node: bool = False, fail_link: bool = False) -> None:
        super().__init__()
        self._fail_node = fail_node
        self._fail_link = fail_link

    async def create_node(self, node: Node) -> Node:
        """Persist a node or return a mismatching node."""
        if self._fail_node:
            return Node(hostname=node.hostname)
        return await super().create_node(node)

    async def create_link(self, link: Link) -> Link:
        """Persist a link or return a mismatching link."""
        if self._fail_link:
            return link.model_copy(update={"speed": 100})
        return await super().create_link(link)


def test_execute_persists_topology() -> None:
    """Test loading the controller topology into the repository."""
    repository = InMemoryNetworkRepository()
    use_case = LoadNetworkUseCase(repository, TestNetworkController())

    asyncio.run(use_case.execute())

    assert repository.nodes == NODES
    assert repository.links == LINKS


def test_execute_raises_when_node_persistence_fails() -> None:
    """Test node persistence failures are surfaced."""
    repository = FailingNetworkRepository(fail_node=True)
    use_case = LoadNetworkUseCase(repository, TestNetworkController())

    with pytest.raises(RuntimeError, match="Failed to persist node switch-a"):
        asyncio.run(use_case.execute())


def test_execute_raises_when_link_persistence_fails() -> None:
    """Test link persistence failures are surfaced."""
    repository = FailingNetworkRepository(fail_link=True)
    use_case = LoadNetworkUseCase(repository, TestNetworkController())

    with pytest.raises(RuntimeError, match="Failed to persist link"):
        asyncio.run(use_case.execute())
