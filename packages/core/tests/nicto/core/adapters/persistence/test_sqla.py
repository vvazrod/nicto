import asyncio

from nicto.core.adapters.persistence.sqla import SqlaNetworkRepository
from nicto.core.entities import Link, Node, Port
from nicto.core.infra.db.models import LinkModel, NodeModel
from nicto.core.infra.db.session import Database
from sqlalchemy import select
from sqlalchemy.orm import selectinload

NODE = Node(
    hostname="switch-a",
    ports=[
        Port(mac_address="00:11:22:33:44:55", name="eth0"),
        Port(mac_address="00:11:22:33:44:56", name="eth1"),
    ],
)
LINK = Link(
    port_a_mac_address="00:11:22:33:44:55",
    port_b_mac_address="00:11:22:33:44:56",
    speed=1000,
    propagation_delay=10,
)


async def _create_database() -> Database:
    database = Database()
    await database.create_schema()
    return database


def test_create_node() -> None:
    """Test node persistence, including its ports."""
    database = asyncio.run(_create_database())
    repository = SqlaNetworkRepository(database)

    try:
        created_node = asyncio.run(repository.create_node(NODE))

        async def get_node() -> NodeModel | None:
            async with database.session() as session:
                return await session.scalar(
                    select(NodeModel)
                    .options(selectinload(NodeModel.ports))
                    .where(NodeModel.hostname == NODE.hostname),
                )

        node_model = asyncio.run(get_node())
        assert created_node == NODE
        assert node_model is not None
        assert node_model.hostname == NODE.hostname
        assert {port.mac_address for port in node_model.ports} == {
            str(port.mac_address) for port in NODE.ports
        }
    finally:
        asyncio.run(database.dispose())


def test_create_link() -> None:
    """Test link persistence."""
    database = asyncio.run(_create_database())
    repository = SqlaNetworkRepository(database)

    try:
        asyncio.run(repository.create_node(NODE))
        created_link = asyncio.run(repository.create_link(LINK))

        async def get_link() -> LinkModel | None:
            async with database.session() as session:
                return await session.scalar(
                    select(LinkModel).where(
                        LinkModel.port_a_mac_address == str(LINK.port_a_mac_address),
                        LinkModel.port_b_mac_address == str(LINK.port_b_mac_address),
                    ),
                )

        link_model = asyncio.run(get_link())
        assert created_link == LINK
        assert link_model is not None
        assert link_model.speed == LINK.speed
        assert link_model.propagation_delay == LINK.propagation_delay
    finally:
        asyncio.run(database.dispose())


def test_get_port_by_mac() -> None:
    """Test retrieving a port through its MAC address."""
    database = asyncio.run(_create_database())
    repository = SqlaNetworkRepository(database)

    try:
        asyncio.run(repository.create_node(NODE))

        port = asyncio.run(repository.get_port_by_mac(NODE.ports[1].mac_address))

        assert port == NODE.ports[1]
    finally:
        asyncio.run(database.dispose())
