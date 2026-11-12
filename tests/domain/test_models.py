import pytest
from pydantic_extra_types.mac_address import MacAddress

from nicto.domain.models import Allocation, Gap, Port, Stream, StreamID

PORT_MAC_ADDRESS = MacAddress("00:11:22:33:44:55")
DESTINATION_MAC_ADDRESS = MacAddress("00:11:22:33:44:56")
TICK_GRANULARITY = 10_000
STREAM_SLOTS = 3


def allocation(start_idx: int, num_slots: int) -> Allocation:
    """Create an allocation belonging to the test port."""
    return Allocation(
        stream_id=StreamID(mac_address=PORT_MAC_ADDRESS, unique_id=1),
        port_mac_address=PORT_MAC_ADDRESS,
        start_idx=start_idx,
        num_slots=num_slots,
    )


def test_port_gaps() -> None:
    """Test gaps include the schedule ranges before, between, and after allocations."""
    port = Port(
        mac_address=PORT_MAC_ADDRESS,
        name="eth0",
        allocations=[allocation(5, 2), allocation(2, 1)],
    )

    assert port.gaps(10) == [
        Gap(start_idx=0, num_slots=2),
        Gap(start_idx=3, num_slots=2),
        Gap(start_idx=7, num_slots=3),
    ]


def test_stream_slots() -> None:
    """Test a stream rounds its transmission time up to whole schedule slots."""
    stream = Stream(
        id=StreamID(mac_address=PORT_MAC_ADDRESS, unique_id=1),
        src_mac_address=PORT_MAC_ADDRESS,
        dst_mac_address=DESTINATION_MAC_ADDRESS,
        max_frame_size=1500,
        max_interval_frames=2,
        interval=1_000,
        max_latency=10_000,
    )

    assert stream.slots(speed=1_000, tick_granularity=TICK_GRANULARITY) == STREAM_SLOTS


@pytest.mark.parametrize(
    ("allocations", "message"),
    [
        ([allocation(2, 3), allocation(4, 2)], "must not overlap"),
        ([allocation(9, 2)], "exceeds the schedule"),
    ],
)
def test_port_gaps_rejects_invalid_allocations(
    allocations: list[Allocation],
    message: str,
) -> None:
    """Test invalid allocation ranges cannot produce ambiguous gaps."""
    port = Port(mac_address=PORT_MAC_ADDRESS, name="eth0", allocations=allocations)

    with pytest.raises(ValueError, match=message):
        port.gaps(10)
