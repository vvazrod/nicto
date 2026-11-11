from pydantic_extra_types.mac_address import MacAddress
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nicto.adapters.persistence.models import LinkModel, NodeModel
from nicto.adapters.persistence.repositories import SqlaNetworkRepository
from nicto.domain.models import Link, Node, Port

NODE = Node(
    hostname="switch-a",
    ports=[
        Port(mac_address=MacAddress("00:11:22:33:44:55"), name="eth0"),
        Port(mac_address=MacAddress("00:11:22:33:44:56"), name="eth1"),
    ],
)
LINK = Link(
    port_a_mac_address=MacAddress("00:11:22:33:44:55"),
    port_b_mac_address=MacAddress("00:11:22:33:44:56"),
    speed=1000,
    propagation_delay=10,
)


async def test_create_node(db_session: AsyncSession) -> None:
    """Test node persistence, including its ports."""
    repository = SqlaNetworkRepository(db_session)

    created_node = await repository.create_node(NODE)

    node_model = await db_session.scalar(
        select(NodeModel)
        .options(selectinload(NodeModel.ports))
        .where(NodeModel.hostname == NODE.hostname)
        .execution_options(populate_existing=True),
    )
    assert created_node == NODE
    assert node_model is not None
    assert node_model.hostname == NODE.hostname
    assert {port.mac_address for port in node_model.ports} == {str(port.mac_address) for port in NODE.ports}


async def test_create_link(db_session: AsyncSession) -> None:
    """Test link persistence."""
    repository = SqlaNetworkRepository(db_session)

    await repository.create_node(NODE)
    created_link = await repository.create_link(LINK)

    link_model = await db_session.scalar(
        select(LinkModel)
        .where(
            LinkModel.port_a_mac_address == str(LINK.port_a_mac_address),
            LinkModel.port_b_mac_address == str(LINK.port_b_mac_address),
        )
        .execution_options(populate_existing=True),
    )
    assert created_link == LINK
    assert link_model is not None
    assert link_model.speed == LINK.speed
    assert link_model.propagation_delay == LINK.propagation_delay


async def test_get_port_by_mac(db_session: AsyncSession) -> None:
    """Test retrieving a port through its MAC address."""
    repository = SqlaNetworkRepository(db_session)
    await repository.create_node(NODE)

    port = await repository.get_port_by_mac(NODE.ports[1].mac_address)

    assert port == NODE.ports[1]


async def test_get_port_by_mac_returns_none_when_not_found(db_session: AsyncSession) -> None:
    """Test a missing MAC address returns no port."""
    repository = SqlaNetworkRepository(db_session)

    port = await repository.get_port_by_mac(MacAddress("00:11:22:33:44:55"))

    assert port is None
