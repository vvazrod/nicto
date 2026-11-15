"""Benchmark path and schedule solving on a spine-leaf network where streams are inserted and removed at random.

The network has two interconnected spines, four leaves connected to both spines, one supervisory node on top of
each spine and a few edge nodes below each leaf. Streams are mostly bottom-up (edge to supervisory), with a minority
of top-down control streams. A total of 100 streams are inserted and 50 are removed, interleaved at random, over
an in-memory SQLite database. This is repeated for each Flexcurve profile.

Two CSV files are written: the path and schedule solving time of every insertion and the number of unfeasible
insertions of each run. Streams that do not fit are expected and are recorded as unfeasible.

Run with ``uv run python benchmarks/flexcurve_spine_leaf_churn.py [--iterations N] [--seed S] [--output-dir DIR]``.
"""

import argparse
import asyncio
import csv
import random
import time
from collections.abc import Sequence
from pathlib import Path

from pydantic_extra_types.mac_address import MacAddress

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

TimesRow = tuple[str, int, int, int, str, int, int, int | None, int | None]


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


async def _run(profile: FlexcurveSolverProfile, iteration: int, seed: int) -> list[TimesRow]:
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
    active: list[StreamID] = []
    try:
        async with session_factory() as session:
            network_repository = SqlaNetworkRepository(session)
            for node in topology.nodes:
                await network_repository.create_node(node)
            for link in topology.links:
                await network_repository.create_link(link)
            await SqlaUnitOfWork(session).commit()

        insertions_left, removals_left = TOTAL_INSERTIONS, TOTAL_REMOVALS
        while insertions_left or removals_left:
            remove = bool(active) and (
                not insertions_left or rng.random() < removals_left / (insertions_left + removals_left)
            )
            if remove:
                index = rng.randrange(len(active))
                active[index], active[-1] = active[-1], active[index]
                async with session_factory() as session:
                    stream_repository = SqlaStreamRepository(session)
                    await RemoveStreamUseCase(stream_repository, SqlaUnitOfWork(session)).execute(active.pop())
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
                    await insert_stream.execute(stream)
                except StreamUnfeasibleError:
                    feasible = 0
                else:
                    feasible = 1
                    active.append(stream.id)
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

    return times


def _write_csv(path: Path, header: Sequence[str], rows: Sequence[Sequence[object]]) -> None:
    with path.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(rows)


async def main(output_dir: Path, iterations: int, seed: int) -> None:
    """Run the benchmark for the minimum latency profile first and then for the maximum throughput one."""
    times: list[TimesRow] = []
    unfeasible_counts: list[tuple[str, int, int, int]] = []
    for profile in (FlexcurveSolverProfile.MIN_LATENCY, FlexcurveSolverProfile.MAX_THROUGHPUT):
        for iteration in range(1, iterations + 1):
            # Both profiles replay the same workload on each iteration
            iteration_times = await _run(profile, iteration, seed + iteration)
            times.extend(iteration_times)
            unfeasible = sum(1 for row in iteration_times if not row[6])
            unfeasible_counts.append((profile.value, iteration, len(iteration_times), unfeasible))
            solving_ms = sum((row[7] or 0) + (row[8] or 0) for row in iteration_times) / 1e6
            print(
                f"{profile.value} [{iteration}/{iterations}]: {solving_ms:.3f} ms solving in total, "
                f"{unfeasible} unfeasible streams",
            )

    times_path = output_dir / "flexcurve_spine_leaf_churn_times.csv"
    unfeasible_path = output_dir / "flexcurve_spine_leaf_churn_unfeasible.csv"
    _write_csv(times_path, TIMES_HEADER, times)
    _write_csv(unfeasible_path, UNFEASIBLE_HEADER, unfeasible_counts)
    print(f"Results saved to {times_path} and {unfeasible_path}")


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
