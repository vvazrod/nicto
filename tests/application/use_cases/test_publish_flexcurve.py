import asyncio
from collections.abc import Sequence

from pydantic_extra_types.mac_address import MacAddress

from nicto.application.ports import FlexcurvePublisher
from nicto.application.use_cases.publish_flexcurve import MAX_FLEXCURVE_STREAM_SLOTS, PublishFlexcurveUseCase
from nicto.application.use_cases.remove_stream import RemoveStreamUseCase
from nicto.config import Config
from nicto.domain.models import Allocation, Node, Port, Stream, StreamID
from tests.application.use_cases.conftest import MockNetworkRepository, MockStreamRepository, MockUnitOfWork

CONFIG = Config(hyperperiod=10_000, tick_granularity=1_000)
MAC_A = MacAddress("00:11:22:33:44:55")
MAC_B = MacAddress("00:11:22:33:44:56")
STREAM_ID = StreamID(mac_address=MAC_A, unique_id=1)
STREAM = Stream(
    id=STREAM_ID,
    src_mac_address=MAC_A,
    dst_mac_address=MAC_B,
    max_frame_size=100,
    max_interval_frames=1,
    interval=10_000,
    max_latency=10_000,
    allocations=[Allocation(stream_id=STREAM_ID, port_mac_address=MAC_A, start_idx=0, num_slots=4)],
)


class MockFlexcurvePublisher(FlexcurvePublisher):
    """Mock publisher that records the published flexcurves by port."""

    def __init__(self, *, fail: bool = False) -> None:
        self.published: dict[str, list[int]] = {}
        self.fail = fail

    async def publish_flexcurve(self, port_mac_address: MacAddress, flexcurve: Sequence[int]) -> None:
        """Record the flexcurve, or raise when configured to fail."""
        if self.fail:
            msg = "unreachable"
            raise ConnectionError(msg)
        self.published[str(port_mac_address)] = list(flexcurve)


def _repository_with_ports() -> MockNetworkRepository:
    repository = MockNetworkRepository()
    repository.nodes = [
        Node(
            hostname="n",
            ports=[
                Port(mac_address=MAC_A, name="a", allocations=STREAM.allocations),
                Port(mac_address=MAC_B, name="b"),
            ],
        ),
    ]
    return repository


def test_publishes_flexcurve_of_each_given_port_once() -> None:
    """Test each port gets the start positions of sizes 1 to 99 from its own gaps."""
    publisher = MockFlexcurvePublisher()
    publication = PublishFlexcurveUseCase(_repository_with_ports(), publisher, CONFIG)

    asyncio.run(publication.publish_ports([MAC_A, MAC_A]))

    assert list(publisher.published) == [str(MAC_A)]
    flexcurve = publisher.published[str(MAC_A)]
    assert len(flexcurve) == MAX_FLEXCURVE_STREAM_SLOTS
    # A single 6-slot gap remains free
    assert flexcurve[:7] == [6, 5, 4, 3, 2, 1, 0]
    assert set(flexcurve[6:]) == {0}


def test_publish_all_covers_every_port() -> None:
    """Test the startup publication includes ports without allocations."""
    publisher = MockFlexcurvePublisher()

    asyncio.run(PublishFlexcurveUseCase(_repository_with_ports(), publisher, CONFIG).publish_all())

    assert set(publisher.published) == {str(MAC_A), str(MAC_B)}
    assert publisher.published[str(MAC_B)][:3] == [10, 9, 8]


def test_removal_publishes_stream_ports_and_survives_publisher_failure(
    stream_repository: MockStreamRepository,
    unit_of_work: MockUnitOfWork,
) -> None:
    """Test removing a stream publishes its ports, and a failing publisher does not fail the removal."""
    stream_repository.streams.append(STREAM)
    publisher = MockFlexcurvePublisher()
    publication = PublishFlexcurveUseCase(_repository_with_ports(), publisher, CONFIG)
    asyncio.run(RemoveStreamUseCase(stream_repository, unit_of_work, publication).execute(STREAM_ID))
    assert list(publisher.published) == [str(MAC_A)]

    stream_repository.streams.append(STREAM)
    failing = PublishFlexcurveUseCase(_repository_with_ports(), MockFlexcurvePublisher(fail=True), CONFIG)
    asyncio.run(RemoveStreamUseCase(stream_repository, unit_of_work, failing).execute(STREAM_ID))
    assert unit_of_work.commits == 2  # noqa: PLR2004
