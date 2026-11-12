from dataclasses import dataclass

from nicto.application.ports import ScheduleSolver
from nicto.application.use_cases.insert_stream import StreamUnfeasibleError
from nicto.config import Config, FlexcurveSolverProfile
from nicto.domain.flexcurve import calculate_flexcurve
from nicto.domain.models import Allocation, Gap, Hop, Stream


@dataclass(slots=True)
class _HopSchedule:
    """The stream size on a hop of the path and the free gaps of its egress port."""

    size: int
    gaps: list[Gap]


@dataclass(frozen=True, slots=True, order=True)
class _Candidate:
    """A feasible placement of the stream on every hop, ordered by latency (in slots) and position."""

    latency: int
    starts: tuple[int, ...]


class FlexcurveSolver(ScheduleSolver):
    """Allocate a stream on the gaps of the schedules of the transmitting ports of its path.

    The stream is placed hop by hop, each transmission starting once the previous one has ended. With the
    ``MAX_THROUGHPUT`` profile the first feasible placement is used, so allocations bunch up at the beginning of
    the schedule. With the ``MIN_LATENCY`` profile every placement is explored and the one with the lowest
    end-to-end latency is used.

    Streams whose interval is shorter than the hyperperiod repeat inside it. The schedule is therefore searched
    over a single interval, where a slot is busy if it is busy in any repetition, and the result is replicated.
    """

    def __init__(self, profile: FlexcurveSolverProfile = FlexcurveSolverProfile.MAX_THROUGHPUT) -> None:
        self._profile = profile

    def find_schedule(
        self,
        stream: Stream,
        path: list[Hop],
        config: Config,
    ) -> list[Allocation]:
        """Find the allocations of a stream on the egress port of every hop of the path."""
        window = stream.interval // config.tick_granularity
        if window <= 0 or config.total_slots % window != 0:
            msg = "Stream interval must divide the configured hyperperiod"
            raise StreamUnfeasibleError(msg)

        hops = self._build_hops(stream, path, config.tick_granularity, window)
        if not hops:
            msg = "The stream path has no hops to schedule"
            raise StreamUnfeasibleError(msg)

        if any(calculate_flexcurve(hop.size, hop.gaps) == 0 for hop in hops):
            msg = "The stream does not fit in the schedule of every port of its path"
            raise StreamUnfeasibleError(msg)

        candidate = self._find_candidate(hops, window, stream.max_latency // config.tick_granularity)
        if candidate is None:
            msg = "No feasible schedule found for the stream"
            raise StreamUnfeasibleError(msg)

        return [
            Allocation(
                stream_id=stream.id,
                port_mac_address=hop.port.mac_address,
                start_idx=(start % window) + repetition * window,
                num_slots=schedule.size,
            )
            for hop, schedule, start in zip(path, hops, candidate.starts, strict=True)
            for repetition in range(config.total_slots // window)
        ]

    def _build_hops(self, stream: Stream, path: list[Hop], tick_granularity: int, window: int) -> list[_HopSchedule]:
        hops: list[_HopSchedule] = []
        for hop in path:
            size = stream.slots(hop.link.speed, tick_granularity)
            if size > window:
                msg = "The stream does not fit in its interval"
                raise StreamUnfeasibleError(msg)
            hops.append(
                _HopSchedule(size=size, gaps=_fold_gaps(hop.port.allocations, window)),
            )
        return hops

    def _find_candidate(self, hops: list[_HopSchedule], window: int, max_latency: int) -> _Candidate | None:
        """Shift the stream along the first port's gaps, keeping the placements within the maximum latency."""
        fit = _find_initial_fit(hops, window)
        if fit is None:
            return None
        starts, gap_nums = fit

        best: _Candidate | None = None
        while True:
            latency = starts[-1] - starts[0] + hops[-1].size
            if latency <= max_latency:
                candidate = _Candidate(latency=latency, starts=tuple(starts))
                if self._profile == FlexcurveSolverProfile.MAX_THROUGHPUT:
                    return candidate
                best = candidate if best is None else min(best, candidate)

            starts[0] += 1
            if starts[0] >= window or not _realign(hops, window, starts, gap_nums):
                return best


def _fold_gaps(allocations: list[Allocation], window: int) -> list[Gap]:
    """Return the free ranges of a window, folding the allocations of the whole schedule into it."""
    busy: list[tuple[int, int]] = []
    for allocation in allocations:
        if allocation.num_slots >= window:
            return []
        start = allocation.start_idx % window
        end = start + allocation.num_slots
        if end > window:
            busy.extend([(start, window), (0, end - window)])
        else:
            busy.append((start, end))

    gaps: list[Gap] = []
    cursor = 0
    for start, end in sorted(busy):
        if start > cursor:
            gaps.append(Gap(start_idx=cursor, num_slots=start - cursor))
        cursor = max(cursor, end)
    if cursor < window:
        gaps.append(Gap(start_idx=cursor, num_slots=window - cursor))
    return gaps


def _find_initial_fit(hops: list[_HopSchedule], window: int) -> tuple[list[int], list[int]] | None:
    """Place the stream on the earliest gaps of every hop, each one after the end of the previous."""
    starts: list[int] = []
    gap_nums: list[int] = []
    search_start = 0
    for hop in hops:
        found = _find_gap(hop, search_start, window)
        if found is None:
            return None
        start, gap_num = found
        starts.append(start)
        gap_nums.append(gap_num)
        search_start = start + hop.size
    return starts, gap_nums


def _realign(hops: list[_HopSchedule], window: int, starts: list[int], gap_nums: list[int]) -> bool:
    """Make the placement of the first hop valid after shifting it, and push the following hops accordingly.

    Return whether a valid placement exists.
    """
    first = hops[0]
    current_gap = first.gaps[gap_nums[0]]
    if current_gap.start_idx + current_gap.num_slots - starts[0] < first.size:
        # The stream no longer fits in the current gap, skip to the next viable one
        for gap_num in range(gap_nums[0] + 1, len(first.gaps)):
            if first.gaps[gap_num].num_slots >= first.size:
                gap_nums[0] = gap_num
                starts[0] = first.gaps[gap_num].start_idx
                break
        else:
            return False

    for i in range(1, len(hops)):
        earliest_start = starts[i - 1] + hops[i - 1].size
        if starts[i] >= earliest_start:
            break
        found = _find_gap(hops[i], earliest_start, window, gap_nums[i])
        if found is None:
            return False
        starts[i], gap_nums[i] = found
    return True


def _find_gap(hop: _HopSchedule, search_start: int, window: int, first_gap_num: int = 0) -> tuple[int, int] | None:
    """Find the earliest start at or after ``search_start`` where the stream fits a gap of the hop.

    ``search_start`` is relative to the beginning of the path and may exceed the window, in which case the
    hop's schedule wraps around. The returned start is relative to the beginning of the path as well.
    """
    port_search_start = search_start % window
    found = _find_gap_relative(hop, port_search_start, first_gap_num)
    if found is None:
        return None

    port_start, gap_num = found
    if port_start < port_search_start:
        port_start += window
    return search_start + port_start - port_search_start, gap_num


def _find_gap_relative(hop: _HopSchedule, start: int, first_gap_num: int) -> tuple[int, int] | None:
    """Find a start within a single window: ``start`` itself if it fits, else the next gap that can hold the stream."""
    num_gaps = len(hop.gaps)
    # If no gap contains or follows ``start``, the search continues from the first gap
    next_gap_num = num_gaps
    for i in range(first_gap_num, num_gaps):
        gap = hop.gaps[i]
        if gap.start_idx <= start < gap.start_idx + gap.num_slots:
            if gap.start_idx + gap.num_slots - start >= hop.size:
                return start, i
            next_gap_num = i + 1
            break
        if gap.start_idx > start:
            next_gap_num = i
            break

    for offset in range(num_gaps):
        gap_num = (next_gap_num + offset) % num_gaps
        if hop.gaps[gap_num].num_slots >= hop.size:
            return hop.gaps[gap_num].start_idx, gap_num
    return None
