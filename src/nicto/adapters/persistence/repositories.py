from pydantic_extra_types.mac_address import MacAddress
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nicto.adapters.persistence.models import LinkModel, NodeModel, PortModel
from nicto.application.ports import NetworkRepository, StreamRepository
from nicto.domain.models import Allocation, Link, Node, Port, Stream


class SqlaNetworkRepository(NetworkRepository):
    """Persist network data using SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_link(self, link: Link) -> Link:
        """Persist a network link."""
        link_model = LinkModel(
            port_a_mac_address=str(link.port_a_mac_address),
            port_b_mac_address=str(link.port_b_mac_address),
            speed=link.speed,
            propagation_delay=link.propagation_delay,
        )
        self._session.add(link_model)
        await self._session.flush()
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
        self._session.add(node_model)
        await self._session.flush()
        return node

    async def get_port_by_mac(self, mac_address: MacAddress) -> Port | None:
        """Retrieve a network port identified by its MAC address."""
        query = (
            select(PortModel)
            .options(selectinload(PortModel.allocations))
            .where(PortModel.mac_address == str(mac_address))
        )
        port_model = await self._session.scalar(query)

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

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_stream(self, stream: Stream) -> Stream:
        """Persist a scheduled stream."""
        raise NotImplementedError
