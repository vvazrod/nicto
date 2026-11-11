import pytest
from pydantic_extra_types.mac_address import MacAddress

from nicto.adapters.solvers.flexcurve import FlexcurveSolver
from nicto.application.use_cases.insert_stream import StreamUnfeasibleError
from nicto.config import Config, FlexcurveSolverProfile
from nicto.domain.models import Allocation, Hop, Link, Port, Stream

CONFIG = Config(hyperperiod=20_000, tick_granularity=1_000)


def _mac(index: int) -> MacAddress:
    return MacAddress(f"00:11:22:33:44:{index:02x}")


def _link(a: int, b: int) -> Link:
    return Link(port_a_mac_address=_mac(a), port_b_mac_address=_mac(b), speed=1_000, propagation_delay=0)


# src(1) - sw(2,3) - dst(4); each stream of 125 bytes takes one 1 us slot per link.
LINKS = [_link(1, 2), _link(3, 4)]
STREAM = Stream(
    src_mac_address=_mac(1),
    dst_mac_address=_mac(4),
    max_frame_size=125,
    max_interval_frames=2,
    interval=20_000,
    max_latency=20_000,
)


def _path(existing: list[Allocation]) -> list[Hop]:
    """Build the path from the egress ports (1 and 3), each holding its existing allocations."""
    return [
        Hop(
            port=Port(
                mac_address=_mac(mac),
                name=f"eth{mac}",
                allocations=[a for a in existing if a.port_mac_address == _mac(mac)],
            ),
            link=link,
        )
        for mac, link in zip((1, 3), LINKS, strict=True)
    ]


def _busy(stream: Stream, mac: int, start: int, slots: int) -> Allocation:
    return Allocation(stream_id=stream.id, port_mac_address=_mac(mac), start_idx=start, num_slots=slots)


def _starts(allocations: list[Allocation]) -> dict[str, int]:
    return {str(a.port_mac_address): a.start_idx for a in allocations}


def test_max_throughput_uses_the_first_feasible_gaps() -> None:
    """Test the stream is placed back to back on the earliest gaps, ignoring ingress ports."""
    existing = [_busy(STREAM, 1, 0, 3), _busy(STREAM, 2, 0, 15), _busy(STREAM, 3, 0, 2)]

    allocations = FlexcurveSolver(FlexcurveSolverProfile.MAX_THROUGHPUT).find_schedule(STREAM, _path(existing), CONFIG)

    assert _starts(allocations) == {str(_mac(1)): 3, str(_mac(3)): 5}
    assert {a.num_slots for a in allocations} == {2}


def test_min_latency_skips_to_a_later_start_with_lower_latency() -> None:
    """Test shifting the first hop shortens the end-to-end latency."""
    existing = [_busy(STREAM, 3, 0, 10), _busy(STREAM, 1, 10, 2)]

    max_throughput = FlexcurveSolver(FlexcurveSolverProfile.MAX_THROUGHPUT).find_schedule(
        STREAM, _path(existing), CONFIG,
    )
    min_latency = FlexcurveSolver(FlexcurveSolverProfile.MIN_LATENCY).find_schedule(STREAM, _path(existing), CONFIG)

    assert _starts(max_throughput) == {str(_mac(1)): 0, str(_mac(3)): 10}
    assert _starts(min_latency) == {str(_mac(1)): 8, str(_mac(3)): 10}


def test_repeated_stream_is_replicated_over_the_hyperperiod() -> None:
    """Test a stream shorter than the hyperperiod is allocated on every repetition."""
    stream = STREAM.model_copy(update={"interval": 10_000})
    existing = [_busy(stream, 1, 11, 1)]

    allocations = FlexcurveSolver().find_schedule(stream, _path(existing), CONFIG)

    assert sorted((str(a.port_mac_address), a.start_idx) for a in allocations) == [
        (str(_mac(1)), 2),
        (str(_mac(1)), 12),
        (str(_mac(3)), 4),
        (str(_mac(3)), 14),
    ]


def test_raises_when_no_gap_fits_the_stream() -> None:
    """Test a full port makes the stream unfeasible."""
    existing = [_busy(STREAM, 3, 0, 19)]

    with pytest.raises(StreamUnfeasibleError, match="does not fit"):
        FlexcurveSolver().find_schedule(STREAM, _path(existing), CONFIG)


def test_raises_when_latency_cannot_be_met() -> None:
    """Test a stream is unfeasible if every placement exceeds its maximum latency."""
    stream = STREAM.model_copy(update={"max_latency": 2_000})
    existing = [_busy(stream, 3, 0, 10)]

    with pytest.raises(StreamUnfeasibleError, match="No feasible"):
        FlexcurveSolver().find_schedule(stream, _path(existing), CONFIG)
