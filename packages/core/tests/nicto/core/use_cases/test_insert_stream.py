import asyncio

import pytest
from nicto.core.config import Config
from nicto.core.entities import Link, Node, Port, Stream
from nicto.core.ports.persistence import NetworkRepository, StreamRepository
from nicto.core.use_cases.insert_stream import (
    InsertStreamUseCase,
    PortNotFoundError,
)
from pydantic_extra_types.mac_address import MacAddress

SOURCE_NODE = Node(
    hostname="source",
    ports=[Port(mac_address="00:11:22:33:44:55", name="eth0")],
)
DESTINATION_NODE = Node(
    hostname="destination",
    ports=[Port(mac_address="00:11:22:33:44:56", name="eth0")],
)
STREAM = Stream(
    src_mac_address=SOURCE_NODE.ports[0].mac_address,
    dst_mac_address=DESTINATION_NODE.ports[0].mac_address,
    max_frame_size=1500,
    max_interval_frames=1,
    interval=1_000,
    max_latency=10_000,
)
CONFIG = Config(hyperperiod=100_000, tick_granularity=1_000)
LINK = Link(
    port_a_mac_address=SOURCE_NODE.ports[0].mac_address,
    port_b_mac_address=DESTINATION_NODE.ports[0].mac_address,
    speed=1_000,
    propagation_delay=0,
)


class RecordingNetworkRepository(NetworkRepository):
    """Record requested endpoint MAC addresses."""

    def __init__(self) -> None:
        self.requested_mac_addresses: list[str] = []

    async def create_link(self, link: Link) -> Link:
        """Satisfy the repository contract."""
        raise NotImplementedError

    async def create_node(self, node: Node) -> Node:
        """Satisfy the repository contract."""
        raise NotImplementedError

    async def get_port_by_mac(self, mac_address: MacAddress) -> Port | None:
        """Record the lookup and return its matching port."""
        self.requested_mac_addresses.append(str(mac_address))
        if mac_address == STREAM.src_mac_address:
            return SOURCE_NODE.ports[0]
        if mac_address == STREAM.dst_mac_address:
            return DESTINATION_NODE.ports[0]
        return None


class RecordingStreamRepository(StreamRepository):
    """Record a persisted stream."""

    def __init__(self) -> None:
        self.streams: list[Stream] = []

    async def create_stream(self, stream: Stream) -> Stream:
        """Record and return the stream."""
        self.streams.append(stream)
        return stream


def test_execute_retrieves_stream_endpoints_before_persisting() -> None:
    """Test stream insertion looks up both endpoint ports."""
    network_repository = RecordingNetworkRepository()
    stream_repository = RecordingStreamRepository()
    use_case = InsertStreamUseCase(network_repository, stream_repository, CONFIG)

    result = asyncio.run(use_case.execute(STREAM))

    assert network_repository.requested_mac_addresses == [
        str(STREAM.src_mac_address),
        str(STREAM.dst_mac_address),
    ]
    assert stream_repository.streams == [STREAM]
    assert isinstance(result, Stream)


def test_execute_raises_when_an_endpoint_port_is_missing() -> None:
    """Test a stream with a missing endpoint port is not persisted."""
    network_repository = RecordingNetworkRepository()
    stream_repository = RecordingStreamRepository()
    use_case = InsertStreamUseCase(network_repository, stream_repository, CONFIG)
    stream = STREAM.model_copy(update={"dst_mac_address": "00:11:22:33:44:57"})

    with pytest.raises(PortNotFoundError, match="source or destination port"):
        asyncio.run(use_case.execute(stream))

    assert stream_repository.streams == []
