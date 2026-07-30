from nicto.core.entities import Allocation, Link, Node, Port, Stream
from nicto.core.infra.db.models import LinkModel, NodeModel, PortModel
from nicto.core.infra.db.session import Database
from nicto.core.ports.persistence import NetworkRepository, StreamRepository
from pydantic_extra_types.mac_address import MacAddress
from sqlalchemy import select
from sqlalchemy.orm import selectinload


class SqlaNetworkRepository(NetworkRepository):
    """Persist network data using SQLAlchemy."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def create_link(self, link: Link) -> Link:
        """Persist a network link."""
        link_model = LinkModel(
            port_a_mac_address=str(link.port_a_mac_address),
            port_b_mac_address=str(link.port_b_mac_address),
            speed=link.speed,
            propagation_delay=link.propagation_delay,
        )
        async with self._database.session() as session:
            session.add(link_model)
            await session.commit()
        return link

    async def create_node(self, node: Node) -> Node:
        """Persist a network node and its ports."""
        node_model = NodeModel(
            hostname=node.hostname,
            ports=[
                PortModel(
                    mac_address=str(port.mac_address),
                    name=port.name,
                )
                for port in node.ports
            ],
        )
        async with self._database.session() as session:
            session.add(node_model)
            await session.commit()
        return node

    async def get_port_by_mac(self, mac_address: MacAddress) -> Port | None:
        """Retrieve a network port identified by its MAC address."""
        query = (
            select(PortModel)
            .options(selectinload(PortModel.allocations))
            .where(PortModel.mac_address == str(mac_address))
        )
        async with self._database.session() as session:
            port_model = await session.scalar(query)

        if port_model is None:
            return None

        return Port(
            mac_address=MacAddress(port_model.mac_address),
            name=port_model.name,
            allocations=[
                Allocation(
                    stream_id=allocation.stream_id,
                    port_mac_address=MacAddress(allocation.port_mac_address),
                    start_idx=allocation.start_idx,
                    num_slots=allocation.num_slots,
                )
                for allocation in port_model.allocations
            ],
        )


class SqlaStreamRepository(StreamRepository):
    """Persist stream data using SQLAlchemy."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def create_stream(self, stream: Stream) -> Stream:
        """Persist a scheduled stream."""
        raise NotImplementedError
