"""Benchmark the runtime of the Flexcurve schedule solver in each of its profiles.

Streams are inserted sequentially over the full path of a four node line network, persisting each one in an
in-memory SQLite database. The time taken to solve each insertion is saved to a single CSV file, with a column
identifying the profile and the iteration.

Run with ``uv run python benchmarks/flexcurve_line_incremental.py [--iterations N] [--output-dir DIR]``.
"""

import argparse
import asyncio
import csv
import time
from pathlib import Path

from pydantic_extra_types.mac_address import MacAddress

from nicto.adapters.persistence.database import create_engine, create_schema, create_session_factory
from nicto.adapters.persistence.repositories import SqlaNetworkRepository, SqlaStreamRepository
from nicto.adapters.persistence.unit_of_work import SqlaUnitOfWork
from nicto.adapters.solvers.flexcurve import FlexcurveSolver
from nicto.config import Config, FlexcurveSolverProfile
from nicto.domain.models import Hop, Link, Node, Port, Stream, StreamID

DATABASE_URL = "sqlite+aiosqlite:///:memory:"
TICK_GRANULARITY = 16
HYPERPERIOD = 160 * 1_000
NUM_STREAMS = 100
VLAN = 100
MAX_FRAME_SIZE = 16
MAX_INTERVAL_FRAMES = 1
LINK_SPEED = 1_000  # Mbps
PROPAGATION_DELAY = 0
NUM_NODES = 4
DEFAULT_OUTPUT_DIR = Path(__file__).parent / "results"
DEFAULT_ITERATIONS = 10

Row = tuple[str, int, int, int]  # profile, iteration, stream number, solving time in ns


def _mac(index: int) -> MacAddress:
    return MacAddress(f"00:11:22:33:44:{index:02x}")


def _line_network() -> tuple[list[Node], list[Link]]:
    """Build a line of nodes: the ends have one port and the inner nodes one port per neighbour."""
    nodes: list[Node] = []
    links: list[Link] = []
    next_mac = 1
    previous_mac: int | None = None
    for node_num in range(NUM_NODES):
        ports: list[Port] = []
        if node_num > 0:
            ports.append(Port(mac_address=_mac(next_mac), name="left"))
            assert previous_mac is not None  # noqa: S101
            links.append(
                Link(
                    port_a_mac_address=_mac(previous_mac),
                    port_b_mac_address=_mac(next_mac),
                    speed=LINK_SPEED,
                    propagation_delay=PROPAGATION_DELAY,
                ),
            )
            next_mac += 1
        if node_num < NUM_NODES - 1:
            ports.append(Port(mac_address=_mac(next_mac), name="right"))
            previous_mac = next_mac
            next_mac += 1
        nodes.append(Node(hostname=f"node{node_num}", ports=ports))
    return nodes, links


async def _run_profile(profile: FlexcurveSolverProfile, iteration: int) -> list[Row]:
    """Insert the streams with a profile and return ``(profile, iteration, stream, solving time in ns)`` rows."""
    config = Config(hyperperiod=HYPERPERIOD, tick_granularity=TICK_GRANULARITY, schedule_profile=profile)
    solver = FlexcurveSolver(profile)
    nodes, links = _line_network()
    src_mac, dst_mac = nodes[0].ports[0].mac_address, nodes[-1].ports[-1].mac_address
    egress_macs = [port.mac_address for node in nodes[:-1] for port in node.ports if port.name == "right"]

    engine = create_engine(DATABASE_URL)
    await create_schema(engine)
    session_factory = create_session_factory(engine)

    rows: list[Row] = []
    try:
        async with session_factory() as session:
            network_repository = SqlaNetworkRepository(session)
            for node in nodes:
                await network_repository.create_node(node)
            for link in links:
                await network_repository.create_link(link)
            await SqlaUnitOfWork(session).commit()

        for stream_num in range(1, NUM_STREAMS + 1):
            stream = Stream(
                id=StreamID(mac_address=src_mac, unique_id=stream_num),
                src_mac_address=src_mac,
                dst_mac_address=dst_mac,
                vlan=VLAN,
                max_frame_size=MAX_FRAME_SIZE,
                max_interval_frames=MAX_INTERVAL_FRAMES,
                interval=HYPERPERIOD,
                max_latency=HYPERPERIOD,
            )

            # Each insertion uses its own session, as an API request does. A session reused across insertions
            # keeps stale allocations of the ports it loaded before, so streams would not see the previous ones.
            async with session_factory() as session:
                network_repository = SqlaNetworkRepository(session)

                # The full line is the path, so the path solver is skipped
                topology_nodes, topology_links = await network_repository.get_topology()
                ports = {port.mac_address: port for node in topology_nodes for port in node.ports}
                path = _build_path(ports, egress_macs, topology_links)

                start = time.perf_counter_ns()
                allocations = solver.find_schedule(stream, path, config)
                elapsed = time.perf_counter_ns() - start

                await SqlaStreamRepository(session).create_stream(
                    stream.model_copy(update={"allocations": allocations}),
                )
                await SqlaUnitOfWork(session).commit()
            rows.append((profile.value, iteration, stream_num, elapsed))
    finally:
        await engine.dispose()
    return rows


def _build_path(ports: dict[MacAddress, Port], egress_macs: list[MacAddress], links: list[Link]) -> list[Hop]:
    """Pair each egress port of the line with the link it transmits on, whichever side of the link it is."""
    link_by_port: dict[MacAddress, Link] = {}
    for link in links:
        link_by_port[link.port_a_mac_address] = link
        link_by_port[link.port_b_mac_address] = link
    return [Hop(port=ports[mac], link=link_by_port[mac]) for mac in egress_macs]


def _write_csv(path: Path, rows: list[Row]) -> None:
    with path.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["profile", "iteration", "stream_number", "solve_time_ns"])
        writer.writerows(rows)


async def main(output_dir: Path, iterations: int) -> None:
    """Run the benchmark for the minimum latency profile first and then for the maximum throughput one."""
    rows: list[Row] = []
    for profile in (FlexcurveSolverProfile.MIN_LATENCY, FlexcurveSolverProfile.MAX_THROUGHPUT):
        for iteration in range(1, iterations + 1):
            iteration_rows = await _run_profile(profile, iteration)
            rows.extend(iteration_rows)
            total_ms = sum(row[3] for row in iteration_rows) / 1e6
            print(f"{profile.value} [{iteration}/{iterations}]: {total_ms:.3f} ms solving in total")

    output_path = output_dir / "flexcurve_line_incremental.csv"
    _write_csv(output_path, rows)
    print(f"Results saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for the CSV file")
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS, help="Runs per profile")
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be at least 1")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    asyncio.run(main(args.output_dir, args.iterations))
