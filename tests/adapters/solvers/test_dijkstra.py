import pytest
from pydantic_extra_types.mac_address import MacAddress

from nicto.adapters.solvers.dijkstra import DijkstraPathSolver
from nicto.application.use_cases.insert_stream import StreamUnfeasibleError
from nicto.domain.models import Link, Node, Port, Stream


def _mac(index: int) -> MacAddress:
    return MacAddress(f"00:11:22:33:44:{index:02x}")


def _node(hostname: str, *indexes: int) -> Node:
    return Node(hostname=hostname, ports=[Port(mac_address=_mac(i), name=f"eth{i}") for i in indexes])


def _link(a: int, b: int, delay: int) -> Link:
    return Link(port_a_mac_address=_mac(a), port_b_mac_address=_mac(b), speed=1_000, propagation_delay=delay)


# src(1) - sw1(2,3,4) - dst(8), with a slower alternative through sw1 port 4 and sw2(5,6).
NODES = [_node("src", 1), _node("sw1", 2, 3, 4), _node("sw2", 5, 6), _node("dst", 8), _node("isolated", 9)]
FAST_LINKS = [_link(1, 2, 10), _link(3, 8, 10)]
SLOW_LINKS = [_link(4, 5, 5), _link(6, 8, 5_000)]
STREAM = Stream(
    src_mac_address=_mac(1),
    dst_mac_address=_mac(8),
    max_frame_size=1500,
    max_interval_frames=1,
    interval=1_000,
    max_latency=100_000,
)


def test_find_path_returns_the_lowest_delay_hops_in_order() -> None:
    """Test the cheapest route is chosen and ordered from source to destination."""
    links = [*SLOW_LINKS, *FAST_LINKS]

    path = DijkstraPathSolver().find_path(STREAM, NODES, links)

    assert [(hop.port.mac_address, hop.link) for hop in path] == [
        (_mac(1), FAST_LINKS[0]),
        (_mac(3), FAST_LINKS[1]),
    ]


def test_find_path_raises_when_destination_is_unreachable() -> None:
    """Test a destination disconnected from the source is unfeasible."""
    stream = STREAM.model_copy(update={"dst_mac_address": _mac(9)})

    with pytest.raises(StreamUnfeasibleError, match="No path"):
        DijkstraPathSolver().find_path(stream, NODES, [*FAST_LINKS, *SLOW_LINKS])
