from pydantic_extra_types.mac_address import MacAddress
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nicto.adapters.persistence.models import AllocationModel, LinkModel, NodeModel, PortModel, StreamModel
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

        return self._to_port(port_model)

    async def get_topology(self) -> tuple[list[Node], list[Link]]:
        """Retrieve all nodes, with their ports' allocations, and links."""
        node_models = await self._session.scalars(
            select(NodeModel).options(selectinload(NodeModel.ports).selectinload(PortModel.allocations)),
        )
        link_models = await self._session.scalars(select(LinkModel))
        nodes = [
            Node(hostname=node_model.hostname, ports=[self._to_port(port) for port in node_model.ports])
            for node_model in node_models
        ]
        links = [
            Link(
                port_a_mac_address=MacAddress(link_model.port_a_mac_address),
                port_b_mac_address=MacAddress(link_model.port_b_mac_address),
                speed=link_model.speed,
                propagation_delay=link_model.propagation_delay,
            )
            for link_model in link_models
        ]
        return nodes, links

    @staticmethod
    def _to_port(port_model: PortModel) -> Port:
        """Convert a port model, whose allocations are loaded, to a domain port."""
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
        """Persist a scheduled stream and its allocations."""
        stream_model = StreamModel(
            id=stream.id,
            src_mac_address=str(stream.src_mac_address),
            dst_mac_address=str(stream.dst_mac_address),
            vlan=stream.vlan,
            priority=stream.priority,
            max_frame_size=stream.max_frame_size,
            max_interval_frames=stream.max_interval_frames,
            interval=stream.interval,
            max_latency=stream.max_latency,
            allocations=[
                AllocationModel(
                    port_mac_address=str(allocation.port_mac_address),
                    start_idx=allocation.start_idx,
                    num_slots=allocation.num_slots,
                )
                for allocation in stream.allocations
            ],
        )
        self._session.add(stream_model)
        await self._session.flush()
        return stream
