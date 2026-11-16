"""Benchmark path and schedule solving on a spine-leaf network where streams are inserted and removed at random.

The network has two interconnected spines, four leaves connected to both spines, one supervisory node on top of
each spine and a few edge nodes below each leaf. Streams are mostly bottom-up (edge to supervisory), with a minority
of top-down control streams. A total of 100 streams are inserted and 50 are removed, interleaved at random, over
an in-memory SQLite database. This is repeated for each Flexcurve profile.

Four CSV files are written: the path and schedule solving time of every insertion, the latency of every feasible
insertion, the contiguous schedule availability of every run, and the number of unfeasible insertions of each run.
Streams that do not fit are expected and are recorded as unfeasible.

Run with ``uv run python benchmarks/flexcurve_spine_leaf_churn.py [--iterations N] [--seed S] [--output-dir DIR]``.
"""

import argparse
import asyncio
import csv
import random
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic_extra_types.mac_address import MacAddress
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nicto.adapters.persistence.database import create_engine, create_schema, create_session_factory
from nicto.adapters.persistence.repositories import SqlaNetworkRepository, SqlaStreamRepository
from nicto.adapters.persistence.unit_of_work import SqlaUnitOfWork
from nicto.adapters.solvers.dijkstra import DijkstraPathSolver
from nicto.adapters.solvers.flexcurve import FlexcurveSolver
from nicto.application.ports import PathSolver, ScheduleSolver
from nicto.application.use_cases.insert_stream import InsertStreamUseCase, StreamUnfeasibleError
from nicto.application.use_cases.remove_stream import RemoveStreamUseCase
from nicto.config import Config, FlexcurveSolverProfile
from nicto.domain.models import Allocation, Hop, Link, Node, Port, Stream, StreamID

DATABASE_URL = "sqlite+aiosqlite:///:memory:"
TICK_GRANULARITY = 16
HYPERPERIOD = 64_000
NUM_SPINES = 2
NUM_LEAVES = 4
EDGE_NODES_PER_LEAF = 2
LINK_SPEED = 1_000  # Mbps
PROPAGATION_DELAY = 0
TOTAL_INSERTIONS = 100
TOTAL_REMOVALS = 50
BOTTOM_UP_PROBABILITY = 0.9
FRAME_SIZES = (64, 512, 1522)
VLAN = 100
DEFAULT_ITERATIONS = 10
DEFAULT_SEED = 0
DEFAULT_OUTPUT_DIR = Path(__file__).parent / "results"

TIMES_HEADER = [
    "profile",
    "iteration",
    "insertion",
    "active_streams",
    "direction",
    "frame_size",
    "feasible",
    "path_time_ns",
    "schedule_time_ns",
]
UNFEASIBLE_HEADER = ["profile", "iteration", "insertions", "unfeasible"]
LATENCIES_HEADER = ["profile", "iteration", "insertion", "frame_size", "latency_ns"]
AVAILABILITY_HEADER = ["profile", "iteration", "contiguous_slots_available_percent"]

TimesRow = tuple[str, int, int, int, str, int, int, int | None, int | None]
LatencyRow = tuple[str, int, int, int, int]
AvailabilityRow = tuple[str, int, float]


class _TimedPathSolver(PathSolver):
    """Record the duration of the last path search of the wrapped solver."""

    def __init__(self, solver: PathSolver) -> None:
        self._solver = solver
        self.elapsed_ns: int | None = None

    def find_path(self, stream: Stream, nodes: list[Node], links: list[Link]) -> list[Hop]:
        start = time.perf_counter_ns()
        try:
            return self._solver.find_path(stream, nodes, links)
        finally:
            self.elapsed_ns = time.perf_counter_ns() - start


class _TimedScheduleSolver(ScheduleSolver):
    """Record the duration of the last schedule search of the wrapped solver."""

    def __init__(self, solver: ScheduleSolver) -> None:
        self._solver = solver
        self.elapsed_ns: int | None = None

    def find_schedule(self, stream: Stream, path: list[Hop], config: Config) -> list[Allocation]:
        start = time.perf_counter_ns()
        try:
            return self._solver.find_schedule(stream, path, config)
        finally:
            self.elapsed_ns = time.perf_counter_ns() - start


class _Topology:
    """Spine-leaf network under construction, assigning sequential MAC addresses to ports."""

    def __init__(self) -> None:
        self.nodes: list[Node] = []
        self.links: list[Link] = []
        self._next_mac = 1

    def add_node(self, hostname: str) -> Node:
        node = Node(hostname=hostname)
        self.nodes.append(node)
        return node

    def connect(self, node_a: Node, node_b: Node) -> None:
        ports = []
        for node in (node_a, node_b):
            mac = MacAddress(f"00:00:00:00:{self._next_mac >> 8:02x}:{self._next_mac & 0xFF:02x}")
            self._next_mac += 1
            ports.append(Port(mac_address=mac, name=f"eth{len(node.ports)}"))
            node.ports.append(ports[-1])
        self.links.append(
            Link(
                port_a_mac_address=ports[0].mac_address,
                port_b_mac_address=ports[1].mac_address,
                speed=LINK_SPEED,
                propagation_delay=PROPAGATION_DELAY,
            ),
        )


def _spine_leaf_network() -> tuple[_Topology, list[Node], list[Node]]:
    """Build the network and return it with its edge nodes and its supervisory nodes."""
    topology = _Topology()
    spines = [topology.add_node(f"spine{i}") for i in range(NUM_SPINES)]
    leaves = [topology.add_node(f"leaf{i}") for i in range(NUM_LEAVES)]
    supervisory = [topology.add_node(f"supervisory{i}") for i in range(NUM_SPINES)]
    edge = [topology.add_node(f"edge{i}_{j}") for i in range(NUM_LEAVES) for j in range(EDGE_NODES_PER_LEAF)]

    for i, spine_a in enumerate(spines):
        for spine_b in spines[i + 1 :]:
            topology.connect(spine_a, spine_b)
    for leaf in leaves:
        for spine in spines:
            topology.connect(leaf, spine)
    for spine, node in zip(spines, supervisory, strict=True):
        topology.connect(spine, node)
    for i, node in enumerate(edge):
        topology.connect(leaves[i // EDGE_NODES_PER_LEAF], node)
    return topology, edge, supervisory


def _random_stream(rng: random.Random, number: int, edge: list[Node], supervisory: list[Node]) -> tuple[Stream, str]:
    """Create a stream that goes mostly bottom-up, as ``(stream, direction)``."""
    bottom_up = rng.random() < BOTTOM_UP_PROBABILITY
    source, destination = (edge, supervisory) if bottom_up else (supervisory, edge)
    src_mac = rng.choice(source).ports[0].mac_address
    dst_mac = rng.choice(destination).ports[0].mac_address
    stream = Stream(
        id=StreamID(mac_address=src_mac, unique_id=number),
        src_mac_address=src_mac,
        dst_mac_address=dst_mac,
        vlan=VLAN,
        max_frame_size=rng.choice(FRAME_SIZES),
        max_interval_frames=1,
        interval=HYPERPERIOD,
        max_latency=HYPERPERIOD,
    )
    return stream, "up" if bottom_up else "down"


def _latency_ns(stream: Stream) -> int:
    """Return the scheduled end-to-end latency, accounting for an interval boundary."""
    first, last = stream.allocations[0], stream.allocations[-1]
    window = stream.interval // TICK_GRANULARITY
    latency_slots = (last.start_idx - first.start_idx) % window + last.num_slots
    return latency_slots * TICK_GRANULARITY


def _latency_row(profile: FlexcurveSolverProfile, iteration: int, insertion: int, stream: Stream) -> LatencyRow:
    """Return a latency result row for a successfully inserted stream."""
    return profile.value, iteration, insertion, stream.max_frame_size, _latency_ns(stream)


def _contiguous_availability_percent(nodes: list[Node], total_slots: int) -> float:
    """Return the mean largest free contiguous block across all port schedules as a percentage."""
    largest_gaps = [
        max((gap.num_slots for gap in port.gaps(total_slots)), default=0) for node in nodes for port in node.ports
    ]
    return 100 * sum(largest_gaps) / (len(largest_gaps) * total_slots)


async def _persist_topology(topology: _Topology, session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Persist the topology before running the churn workload."""
    async with session_factory() as session:
        network_repository = SqlaNetworkRepository(session)
        for node in topology.nodes:
            await network_repository.create_node(node)
        for link in topology.links:
            await network_repository.create_link(link)
        await SqlaUnitOfWork(session).commit()


def _update_topology_allocations(topology: _Topology, stream: Stream, operation: Literal["add", "remove"]) -> None:
    """Add or remove a stream's allocations from the topology mirror."""
    ports = {port.mac_address: port for node in topology.nodes for port in node.ports}
    for allocation in stream.allocations:
        if operation == "add":
            ports[allocation.port_mac_address].allocations.append(allocation)
        else:
            ports[allocation.port_mac_address].allocations.remove(allocation)


async def _remove_stream(
    stream_id: StreamID,
    topology: _Topology,
    scheduled_streams: dict[StreamID, Stream],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Remove a stream from persistence and the topology mirror."""
    async with session_factory() as session:
        stream_repository = SqlaStreamRepository(session)
        await RemoveStreamUseCase(stream_repository, SqlaUnitOfWork(session)).execute(stream_id)
    _update_topology_allocations(topology, scheduled_streams.pop(stream_id), operation="remove")


async def _run(
    profile: FlexcurveSolverProfile,
    iteration: int,
    seed: int,
) -> tuple[list[TimesRow], list[LatencyRow], AvailabilityRow]:
    """Run the insertions and removals of one iteration with a profile.

    Every operation uses its own session, as every API request does. Reusing one session would let it keep stale
    allocations of the ports it loaded before, which makes the results depend on garbage collection.
    """
    config = Config(hyperperiod=HYPERPERIOD, tick_granularity=TICK_GRANULARITY, schedule_profile=profile)
    path_solver = _TimedPathSolver(DijkstraPathSolver(config))
    schedule_solver = _TimedScheduleSolver(FlexcurveSolver(profile))
    topology, edge, supervisory = _spine_leaf_network()
    rng = random.Random(seed)  # noqa: S311

    engine = create_engine(DATABASE_URL)
    await create_schema(engine)
    session_factory = create_session_factory(engine)

    times: list[TimesRow] = []
    latencies: list[LatencyRow] = []
    active: list[StreamID] = []
    scheduled_streams: dict[StreamID, Stream] = {}
    try:
        await _persist_topology(topology, session_factory)

        insertions_left, removals_left = TOTAL_INSERTIONS, TOTAL_REMOVALS
        while insertions_left or removals_left:
            remove = bool(active) and (
                not insertions_left or rng.random() < removals_left / (insertions_left + removals_left)
            )
            if remove:
                index = rng.randrange(len(active))
                active[index], active[-1] = active[-1], active[index]
                stream_id = active.pop()
                await _remove_stream(stream_id, topology, scheduled_streams, session_factory)
                removals_left -= 1
                continue
            if not insertions_left:
                break

            insertions_left -= 1
            number = TOTAL_INSERTIONS - insertions_left
            stream, direction = _random_stream(rng, number, edge, supervisory)
            path_solver.elapsed_ns = schedule_solver.elapsed_ns = None
            active_before = len(active)
            async with session_factory() as session:
                insert_stream = InsertStreamUseCase(
                    SqlaNetworkRepository(session),
                    SqlaStreamRepository(session),
                    SqlaUnitOfWork(session),
                    path_solver,
                    schedule_solver,
                    config,
                )
                try:
                    inserted_stream = await insert_stream.execute(stream)
                except StreamUnfeasibleError:
                    feasible = 0
                else:
                    feasible = 1
                    active.append(stream.id)
                    scheduled_streams[stream.id] = inserted_stream
                    _update_topology_allocations(topology, inserted_stream, operation="add")
                    latencies.append(_latency_row(profile, iteration, number, inserted_stream))
            times.append(
                (
                    profile.value,
                    iteration,
                    number,
                    active_before,
                    direction,
                    stream.max_frame_size,
                    feasible,
                    path_solver.elapsed_ns,
                    schedule_solver.elapsed_ns,
                ),
            )

    finally:
        await engine.dispose()

    availability = (profile.value, iteration, _contiguous_availability_percent(topology.nodes, config.total_slots))
    return times, latencies, availability


def _write_csv(path: Path, header: Sequence[str], rows: Sequence[Sequence[object]]) -> None:
    with path.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(rows)


async def main(output_dir: Path, iterations: int, seed: int) -> None:
    """Run the benchmark for the minimum latency profile first and then for the maximum throughput one."""
    times: list[TimesRow] = []
    latencies: list[LatencyRow] = []
    availabilities: list[AvailabilityRow] = []
    unfeasible_counts: list[tuple[str, int, int, int]] = []
    for profile in (FlexcurveSolverProfile.MIN_LATENCY, FlexcurveSolverProfile.MAX_THROUGHPUT):
        for iteration in range(1, iterations + 1):
            # Both profiles replay the same workload on each iteration
            iteration_times, iteration_latencies, availability = await _run(profile, iteration, seed + iteration)
            times.extend(iteration_times)
            latencies.extend(iteration_latencies)
            availabilities.append(availability)
            unfeasible = sum(1 for row in iteration_times if not row[6])
            unfeasible_counts.append((profile.value, iteration, len(iteration_times), unfeasible))
            solving_ms = sum((row[7] or 0) + (row[8] or 0) for row in iteration_times) / 1e6
            print(
                f"{profile.value} [{iteration}/{iterations}]: {solving_ms:.3f} ms solving in total, "
                f"{unfeasible} unfeasible streams",
            )

    times_path = output_dir / "flexcurve_spine_leaf_churn_times.csv"
    latencies_path = output_dir / "flexcurve_spine_leaf_churn_latencies.csv"
    availability_path = output_dir / "flexcurve_spine_leaf_churn_availability.csv"
    unfeasible_path = output_dir / "flexcurve_spine_leaf_churn_unfeasible.csv"
    _write_csv(times_path, TIMES_HEADER, times)
    _write_csv(latencies_path, LATENCIES_HEADER, latencies)
    _write_csv(availability_path, AVAILABILITY_HEADER, availabilities)
    _write_csv(unfeasible_path, UNFEASIBLE_HEADER, unfeasible_counts)
    print(f"Results saved to {times_path}, {latencies_path}, {availability_path}, and {unfeasible_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for the CSV files")
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS, help="Runs per profile")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Base seed of the random workloads")
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be at least 1")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    asyncio.run(main(args.output_dir, args.iterations, args.seed))
