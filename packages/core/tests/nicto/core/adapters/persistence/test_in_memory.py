import asyncio

from nicto.core.adapters.persistence.in_memory import InMemoryNetworkRepository
from nicto.core.entities import Node, Port
from pydantic_extra_types.mac_address import MacAddress

NODE = Node(
    hostname="switch-a",
    ports=[
        Port(mac_address="00:11:22:33:44:55", name="eth0"),
        Port(mac_address="00:11:22:33:44:56", name="eth1"),
    ],
)


def test_get_port_by_mac() -> None:
    """Test retrieving a port through its MAC address."""
    repository = InMemoryNetworkRepository()
    asyncio.run(repository.create_node(NODE))

    port = asyncio.run(repository.get_port_by_mac(NODE.ports[1].mac_address))

    assert port == NODE.ports[1]


def test_get_port_by_mac_returns_none_when_not_found() -> None:
    """Test a missing MAC address returns no port."""
    repository = InMemoryNetworkRepository()

    port = asyncio.run(repository.get_port_by_mac(MacAddress("00:11:22:33:44:55")))

    assert port is None
